import json
import os
import tempfile
import unittest
from unittest.mock import patch

import db
from crm_connector import build_lead_payload, queue_lead, send_outbox_item
from lead_review import get_review, save_review


class BusinessSuggestionTests(unittest.TestCase):
    def test_explicit_quoted_company_name_is_a_claim_not_verified_identity(self):
        from business_profiles import suggest_business_profile
        result = suggest_business_profile('☀️ لیست موجودی\n«شرکت ExampleSolar؛ همراه شما در مسیر انرژی پاک»', 'stock_availability')
        self.assertEqual(result['declared_name'], 'ExampleSolar')
        self.assertEqual(result['entity_type'], 'company')
        self.assertEqual(result['roles'], ['supplier'])
        self.assertEqual(result['contact_verification'], 'unverified')
        self.assertEqual(result['name_origin'], 'message_text')

    def test_persian_company_name_preserved_without_legal_name_guess(self):
        from business_profiles import suggest_business_profile
        result = suggest_business_profile('شرکت انرژی نمونه؛ تأمین تجهیزات', 'supplier_seller')
        self.assertEqual(result['declared_name'], 'انرژی نمونه')

    def test_no_person_or_company_is_inferred_from_sender(self):
        from business_profiles import suggest_business_profile
        for text in ('خریدار پنل هستیم', 'برای شرکت در مناقصه تماس بگیرید', 'اینورتر برند ExampleSolar'):
            with self.subTest(text=text):
                result = suggest_business_profile(text, 'buyer_demand')
                self.assertEqual(result['declared_name'], '')
                self.assertEqual(result['entity_type'], 'unknown')
                self.assertEqual(result['roles'], ['buyer'])


class BusinessReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = db.DB_PATH
        db.DB_PATH = os.path.join(self.tmp.name, 'business.db')
        db.init_db()
        with db.connect() as con:
            self.mid = con.execute('''INSERT INTO messages
                (external_id,chat_name,sender_name,text,category)
                VALUES(?,?,?,?,?)''', ('sample-1', 'گروه نمایشی', 'ادمین گروه',
                'شرکت ExampleSolar؛ فروش تجهیزات تماس 09123456789 www.example.com', 'supplier_seller')).lastrowid
            self.row = dict(con.execute('SELECT * FROM messages WHERE id=?', (self.mid,)).fetchone())
        self.profile = dict(entity_type='company', declared_name='ExampleSolar', roles=['supplier'],
                            contact_person='', contact_verification='unverified', verification_note='')

    def tearDown(self):
        db.DB_PATH = self.old_path
        self.tmp.cleanup()

    def save(self, **kwargs):
        values = dict(review_status='selected', business_profile=self.profile, contact='09123456789')
        values.update(kwargs)
        return save_review(self.mid, 'reviewer-test', values)

    def test_business_profile_is_saved_and_legacy_update_preserves_it(self):
        self.save()
        self.assertEqual(get_review(self.mid)['business_profile']['declared_name'], 'ExampleSolar')
        save_review(self.mid, 'reviewer-test', {'review_status': 'reviewed', 'notes': 'legacy client'})
        self.assertEqual(get_review(self.mid)['business_profile']['roles'], ['supplier'])

    def test_invalid_role_type_and_forged_verifier_are_rejected(self):
        for change in ({'roles': ['admin']}, {'entity_type': 'bank'}, {'verified_by': 'someone'},
                       {'roles': 'supplier'}, {'declared_name': 'a' * 201}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.save(business_profile={**self.profile, **change})

    def test_selected_business_requires_name_type_and_role(self):
        for change in ({'declared_name': ''}, {'entity_type': 'unknown'}, {'roles': []}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.save(business_profile={**self.profile, **change})

    def test_contact_confirmation_requires_evidence_and_primary_contact(self):
        confirmed = {**self.profile, 'contact_verification': 'confirmed'}
        for contact, note in (('09123456789', ''), ('', 'تماس تلفنی انجام شد'), ('نام نامشخص', 'بررسی شد')):
            with self.subTest(contact=contact, note=note):
                with self.assertRaises(ValueError):
                    self.save(contact=contact, business_profile={**confirmed, 'verification_note': note})
        row = self.save(business_profile={**confirmed, 'verification_note': 'تعلق شماره با تماس بررسی شد'})
        self.assertEqual(row['business_profile']['contact_verification'], 'confirmed')
        self.assertEqual(row['reviewed_by'], 'reviewer-test')

    def test_confirmation_audit_survives_other_reviewer_notes_edit(self):
        self.save(business_profile={**self.profile, 'contact_verification': 'confirmed', 'verification_note': 'تماس بررسی شد'})
        save_review(self.mid, 'other-reviewer', {'review_status': 'reviewed', 'notes': 'یادداشت جدید'})
        row = get_review(self.mid)
        self.assertEqual(row['business_profile']['contact_verified_by'], 'reviewer-test')
        self.assertTrue(row['business_profile']['contact_verified_at'])
        self.assertEqual(row['contact'], '09123456789')

    def test_primary_contact_change_does_not_inherit_old_confirmation(self):
        self.save(business_profile={**self.profile, 'contact_verification': 'confirmed', 'verification_note': 'تماس بررسی شد'})
        save_review(self.mid, 'other-reviewer', {'review_status': 'reviewed', 'contact': '09351234567'})
        row = get_review(self.mid)
        self.assertEqual(row['business_profile']['contact_verification'], 'unverified')
        self.assertIsNone(row['business_profile']['contact_verified_by'])

    def test_business_payload_routes_supplier_without_creating_company(self):
        review = self.save()
        p = build_lead_payload(self.row, review)
        context = p['raw_payload']['business_context']
        self.assertEqual(context['schema'], 'satno.market-party.v1')
        self.assertEqual(context['intended_intake'], 'supplier_intake')
        self.assertEqual(context['requested_action'], 'resolve_or_create_after_review')
        self.assertEqual(context['party']['declared_name'], 'ExampleSolar')
        self.assertEqual(context['review']['reviewed_by'], 'reviewer-test')
        self.assertEqual(context['source']['message_id'], self.mid)
        self.assertEqual(p['organization_name'], 'ExampleSolar')
        self.assertNotIn('contact_name', p)
        self.assertFalse(any(c['ownership_verified'] for c in p['raw_payload']['extracted']['ad_contacts']))

    def test_buyer_dual_role_and_person_are_separate_routes(self):
        for roles, route in ((['buyer'], 'sales_lead_intake'), (['supplier', 'buyer'], 'dual_role_intake')):
            review = self.save(business_profile={**self.profile, 'roles': roles, 'entity_type': 'person', 'declared_name': 'شخص نمونه'})
            payload = build_lead_payload(self.row, review)
            self.assertEqual(payload['raw_payload']['business_context']['intended_intake'], route)
            self.assertNotIn('organization_name', payload)
            self.assertEqual(payload['contact_name'], 'شخص نمونه')

    def test_new_business_contract_is_queued_but_cannot_reach_legacy_receiver(self):
        self.save()
        queued = queue_lead(self.mid, 'reviewer-test')
        with patch.dict(os.environ, {'SATNO_CRM_LEAD_URL': 'http://127.0.0.1:9/ingest', 'SATNO_BALE_MARKET_INGEST_TOKEN': 'x' * 40}):
            with patch('crm_connector.urllib_request.urlopen', side_effect=AssertionError('Live call forbidden')) as network:
                result = send_outbox_item(queued['id'])
                self.assertEqual(result['status'], 'blocked')
                self.assertEqual(result['reason'], 'business_contract_pending')
                network.assert_not_called()
        with db.connect() as con:
            row = con.execute('SELECT attempts,payload FROM crm_lead_outbox WHERE id=?', (queued['id'],)).fetchone()
        self.assertEqual(row['attempts'], 0)
        self.assertIn('business_context', json.loads(row['payload'])['raw_payload'])

    def test_old_queued_packet_cannot_bypass_new_business_review_gate(self):
        save_review(self.mid, 'old-reviewer', {'review_status': 'selected'})
        queued = queue_lead(self.mid, 'old-reviewer')
        self.save()
        with patch.dict(os.environ, {'SATNO_CRM_LEAD_URL': 'http://127.0.0.1:9/ingest', 'SATNO_BALE_MARKET_INGEST_TOKEN': 'x' * 40}):
            with patch('crm_connector.urllib_request.urlopen', side_effect=OSError('Unexpected network')) as network:
                self.assertEqual(send_outbox_item(queued['id']).get('reason'), 'business_contract_pending')
                network.assert_not_called()

    def test_handoff_download_requires_staff_permission_and_returns_snapshot(self):
        from fastapi.testclient import TestClient
        from main import app
        from auth import create_user
        self.save()
        queued = queue_lead(self.mid, 'reviewer-test')
        url = '/api/crm/outbox/' + str(queued['id']) + '/handoff'
        with TestClient(app) as client:
            self.assertEqual(client.get(url).status_code, 401)
            for role in ('viewer', 'sales'):
                create_user(role, 'SyntheticPassword123!', role)
                client.post('/api/auth/login', json={'username': role, 'password': 'SyntheticPassword123!'})
                response = client.get(url)
                self.assertEqual(response.status_code, 403 if role == 'viewer' else 200)
                if role == 'sales':
                    self.assertEqual(response.json(), json.loads(queued['payload']))
                    self.assertIn('attachment;', response.headers['content-disposition'])
                    self.assertEqual(response.headers['cache-control'], 'no-store')
                client.post('/api/auth/logout')

    def test_market_search_finds_reviewed_party_name_and_preserves_ad(self):
        from fastapi.testclient import TestClient
        from main import app
        from auth import create_user
        self.save(business_profile={**self.profile, 'declared_name': 'بازرگانی نمونه بررسی‌شده'})
        create_user('sales', 'SyntheticPassword123!', 'sales')
        with TestClient(app) as client:
            client.post('/api/auth/login', json={'username': 'sales', 'password': 'SyntheticPassword123!'})
            rows = client.get('/api/messages', params={'q': 'بازرگانی نمونه بررسی‌شده'}).json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['business_profile']['declared_name'], 'بازرگانی نمونه بررسی‌شده')
        self.assertEqual(rows[0]['text'], self.row['text'])

    def test_outbox_indicator_matches_gate_for_old_packet_with_new_review(self):
        from operations_routes import crm_outbox
        save_review(self.mid, 'old-reviewer', {'review_status': 'selected'})
        queue_lead(self.mid, 'old-reviewer')
        self.save()
        item = crm_outbox(user={})[0]
        self.assertEqual(item['delivery_blocked_reason'], 'business_contract_pending')
        self.assertIsNone(item['business_context'])

    def test_sent_snapshot_is_immutable_across_review_and_schema_initialization(self):
        self.save()
        first = queue_lead(self.mid, 'reviewer-test')
        with db.connect() as con:
            con.execute("UPDATE crm_lead_outbox SET status='sent' WHERE id=?", (first['id'],))
        self.save(business_profile={**self.profile, 'roles': ['buyer']})
        db.init_db()
        second = queue_lead(self.mid, 'another-reviewer')
        self.assertEqual(second['id'], first['id'])
        self.assertEqual(second['payload'], first['payload'])
        self.assertTrue(send_outbox_item(first['id'])['already_sent'])
        with db.connect() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM messages').fetchone()[0], 1)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM crm_lead_outbox').fetchone()[0], 1)

    def test_malformed_profile_types_fail_validation_without_server_type_errors(self):
        for change in ({'entity_type': []}, {'contact_verification': {}}, {'roles': [{}]},
                       {'declared_name': ['Name']}, {'contact_verified_at': 'forged'}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self.save(business_profile={**self.profile, **change})

    def test_existing_review_data_survives_idempotent_schema_upgrade(self):
        save_review(self.mid, 'old-reviewer', {'review_status': 'reviewed', 'notes': 'keep'})
        with db.connect() as con:
            # Reproduce the pre-feature schema without touching any operational database.
            con.execute('ALTER TABLE lead_reviews DROP COLUMN business_profile')
        db.init_db()
        db.init_db()
        self.assertEqual(get_review(self.mid)['notes'], 'keep')
        self.assertIsNone(get_review(self.mid)['business_profile'])
