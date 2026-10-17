import json
import os
import tempfile
import unittest
from unittest.mock import patch

import db
from crm_connector import build_lead_payload, queue_lead, send_outbox_item
from lead_review import save_review
from operations_routes import review_messages, crm_outbox


class ContactCRMTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = db.DB_PATH
        db.DB_PATH = os.path.join(self.tmp.name, 'contacts.db')
        db.init_db()
        self.text = ('فروش اینورتر تماس: ۰۹۱۲۳۴۵۶۷۸۹ '
                     'https://wa.me/989123456789 بله: @ad_supplier '
                     'sales@example.com www.example.com')
        with db.connect() as con:
            self.mid = con.execute('''INSERT INTO messages
                (text,chat_name,sender_name,sender_id,sender_username,sender_link,category)
                VALUES(?,?,?,?,?,?,?)''', (self.text, 'گروه نمایشی', 'ادمین گروه', '77',
                'group_admin', 'https://ble.ir/group_admin', 'supplier_seller')).lastrowid
        with db.connect() as con:
            self.row = dict(con.execute('SELECT * FROM messages WHERE id=?', (self.mid,)).fetchone())

    def tearDown(self):
        db.DB_PATH = self.old_path
        self.tmp.cleanup()

    def selected(self, contact=None):
        return save_review(self.mid, 'sales-test', {'review_status': 'selected', 'contact': contact})

    def test_review_api_contains_message_contacts_and_publisher_role(self):
        row = review_messages(message_id=self.mid, user={})[0]
        self.assertEqual(row['sender_contact_role'], 'publisher')
        self.assertIn('bale', [c['kind'] for c in row['ad_contacts']])
        self.assertEqual(row['text'], self.text)

    def test_payload_maps_phone_email_and_retains_links_without_owner_guess(self):
        p = build_lead_payload(self.row, self.selected())
        self.assertEqual(p['contact_phone'], '09123456789')
        self.assertEqual(p['contact_email'], 'sales@example.com')
        self.assertNotIn('contact_name', p)
        raw = p['raw_payload']
        self.assertEqual(raw['message']['sender_contact_role'], 'publisher')
        contacts = raw['extracted']['ad_contacts']
        self.assertIn('https://ble.ir/ad_supplier', [c['href'] for c in contacts])
        self.assertTrue(all(not c['ownership_verified'] for c in contacts))

    def test_reviewed_link_is_not_put_in_phone_field(self):
        p = build_lead_payload(self.row, self.selected('https://ble.ir/verified_supplier'))
        self.assertNotIn('contact_phone', p)
        self.assertEqual(p['raw_payload']['review']['contact'], 'https://ble.ir/verified_supplier')
        self.assertEqual(p['raw_payload']['review']['ad_contacts'][0]['kind'], 'bale')

    def test_reviewed_email_maps_to_email_not_phone(self):
        p = build_lead_payload(self.row, self.selected('reviewed@example.org'))
        self.assertEqual(p['contact_email'], 'reviewed@example.org')
        self.assertNotIn('contact_phone', p)

    def test_stale_classifier_phone_not_used_as_contact(self):
        row = {**self.row, 'text': 'مدل SUN-80K', 'phones': '["09120000000"]'}
        self.assertNotIn('contact_phone', build_lead_payload(row))

    def test_outbox_displays_snapshot_not_new_message_text(self):
        self.selected()
        queued = queue_lead(self.mid, 'sales-test')
        with db.connect() as con:
            con.execute('UPDATE messages SET text=? WHERE id=?', ('تماس 09351234567', self.mid))
        row = crm_outbox(user={})[0]
        self.assertEqual(row['id'], queued['id'])
        self.assertIn('09123456789', [c['value'] for c in row['ad_contacts']])
        self.assertNotIn('09351234567', [c['value'] for c in row['ad_contacts']])
        self.assertEqual(row['reviewed_contact'], None)

    def test_queue_does_not_send_when_live_crm_is_disabled(self):
        self.selected()
        queued = queue_lead(self.mid, 'sales-test')
        with patch.dict(os.environ, {'SATNO_CRM_LEAD_URL': '', 'SATNO_BALE_MARKET_INGEST_TOKEN': ''}):
            with patch('crm_connector.urllib_request.urlopen') as network:
                result = send_outbox_item(queued['id'])
                network.assert_not_called()
        self.assertEqual(result['status'], 'queued')
        self.assertIn('ad_contacts', json.loads(queued['payload'])['raw_payload']['extracted'])

    def test_rejected_review_cannot_refresh_existing_queue(self):
        self.selected()
        first = queue_lead(self.mid, 'sales-test')
        save_review(self.mid, 'sales-test', {'review_status': 'rejected'})
        with self.assertRaisesRegex(ValueError, 'reviewed and selected'):
            queue_lead(self.mid, 'sales-test')
        with db.connect() as con:
            payload = con.execute('SELECT payload FROM crm_lead_outbox WHERE id=?', (first['id'],)).fetchone()[0]
        self.assertEqual(payload, first['payload'])

    def test_contacts_are_not_exposed_or_queued_without_correct_role(self):
        from auth import create_user
        from main import app
        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/review/messages').status_code, 401)
            self.assertEqual(client.get('/api/crm/outbox').status_code, 401)
            for role in ('viewer', 'sales'):
                create_user('contact-' + role, 'SyntheticOnlyPassword123!', role)
                self.assertEqual(client.post('/api/auth/login', json={
                    'username': 'contact-' + role, 'password': 'SyntheticOnlyPassword123!'
                }).status_code, 200)
                self.selected()
                response = client.post('/api/leads/' + str(self.mid) + '/queue')
                self.assertEqual(response.status_code, 403 if role == 'viewer' else 200)
                client.post('/api/auth/logout')

    def test_rejected_lead_is_not_sent_from_old_queue(self):
        self.selected()
        queued = queue_lead(self.mid, 'sales-test')
        save_review(self.mid, 'sales-test', {'review_status': 'rejected'})
        with patch.dict(os.environ, {'SATNO_CRM_LEAD_URL': 'http://127.0.0.1:9/ingest', 'SATNO_BALE_MARKET_INGEST_TOKEN': 'x' * 40}):
            with patch('crm_connector.urllib_request.urlopen', side_effect=OSError('Unexpected network')) as network:
                result = send_outbox_item(queued['id'])
                self.assertEqual(result['status'], 'blocked')
                network.assert_not_called()

    def test_reviewer_contact_keeps_separate_provenance(self):
        p = build_lead_payload(self.row, self.selected('09351234567'))
        c = p['raw_payload']['review']['ad_contacts'][0]
        self.assertEqual(c['origin'], 'reviewer_input')
        self.assertFalse(c['ownership_verified'])
        self.assertEqual(p['raw_payload']['extracted']['ad_contacts'][0]['origin'], 'message_text')
        queue_lead(self.mid, 'sales-test')
        self.assertEqual(crm_outbox(user={})[0]['reviewed_contacts'][0]['origin'], 'reviewer_input')
