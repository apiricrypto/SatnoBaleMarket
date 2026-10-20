import os
import tempfile
import shutil
import unittest
from urllib.parse import urlsplit, parse_qs
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

import db
from auth import create_user, authenticate_user, create_session, resolve_session, update_user, change_own_password

SETTINGS = {'SATNO_PUBLIC_BASE_URL': 'https://market.example.com', 'SATNO_SMTP_HOST': 'smtp.example.com',
            'SATNO_SMTP_PORT': '587', 'SATNO_SMTP_SECURITY': 'starttls',
            'SATNO_SMTP_USERNAME': 'mailer@example.com', 'SATNO_SMTP_PASSWORD': 'synthetic-only',
            'SATNO_SMTP_FROM': 'mailer@example.com'}


class PasswordRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = db.DB_PATH
        db.DB_PATH = os.path.join(self.tmp.name, 'recovery.db')
        self.env = patch.dict(os.environ, SETTINGS)
        self.env.start()
        create_user('admin', 'PreviousPassword123!', 'admin', email='admin@example.com')
        self.uid = authenticate_user('admin', 'PreviousPassword123!')['id']

    def tearDown(self):
        db.DB_PATH = self.previous
        self.env.stop()
        self.tmp.cleanup()

    def issue(self, email='admin@example.com'):
        from password_reset import deliver_reset_email
        links = []
        with patch('password_reset.send_reset_email', side_effect=lambda recipient, link: links.append(link)):
            deliver_reset_email(email)
        return parse_qs(urlsplit(links[0]).fragment)['token'][0] if links else None

    def test_reset_works_for_every_role_and_revokes_all_sessions(self):
        from password_reset import reset_password
        for role in ('admin', 'sales', 'viewer'):
            if role != 'admin':
                create_user(role, 'PreviousPassword123!', role, email=role+'@example.com')
            user = authenticate_user(role, 'PreviousPassword123!')
            session = create_session(user['id'])
            other = create_session(user['id'])
            token = self.issue(role+'@example.com')
            reset_password(token, 'ReplacementPassword123!')
            self.assertIsNone(authenticate_user(role, 'PreviousPassword123!'))
            self.assertIsNotNone(authenticate_user(role, 'ReplacementPassword123!'))
            self.assertIsNone(resolve_session(session))
            self.assertIsNone(resolve_session(other))
            with self.assertRaises(ValueError):
                reset_password(token, 'AnotherPassword123!')

    def test_tokens_are_hashed_expire_and_new_link_invalidates_old(self):
        from password_reset import reset_password
        first = self.issue()
        second = self.issue()
        with db.connect() as con:
            tokens = [r['token_hash'] for r in con.execute('SELECT token_hash FROM staff_password_resets')]
            self.assertNotIn(second, tokens)
            self.assertTrue(all(len(t) == 64 for t in tokens))
            con.execute('UPDATE staff_password_resets SET expires_at=?', ((datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),))
        for token in (first, second, 'x' * 43):
            with self.assertRaises(ValueError):
                reset_password(token, 'ReplacementPassword123!')

    def test_email_change_admin_reset_and_own_password_change_revoke_links(self):
        from password_reset import reset_password
        for action in (
            lambda: update_user(self.uid, email='new@example.com'),
            lambda: update_user(self.uid, password='AdminChangedPassword123!'),
            lambda: change_own_password(self.uid, 'AdminChangedPassword123!', 'OwnChangedPassword123!'),
        ):
            with db.connect() as con:
                current = con.execute('SELECT email FROM staff_users WHERE id=?', (self.uid,)).fetchone()[0]
            token = self.issue(current)
            action()
            with self.assertRaises(ValueError):
                reset_password(token, 'ReplacementPassword123!')

    def test_unknown_inactive_and_missing_email_send_nothing(self):
        from password_reset import deliver_reset_email
        create_user('no-email', 'PreviousPassword123!', 'sales')
        create_user('another-admin', 'PreviousPassword123!', 'admin')
        update_user(self.uid, is_active=False)
        with patch('password_reset.send_reset_email') as send:
            for email in ('missing@example.com', 'admin@example.com'):
                deliver_reset_email(email)
            send.assert_not_called()

    def test_failed_delivery_does_not_leave_usable_token_or_expose_error(self):
        from password_reset import deliver_reset_email
        with patch('password_reset.send_reset_email', side_effect=OSError('private SMTP details')):
            deliver_reset_email('admin@example.com')
        with db.connect() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM staff_password_resets WHERE used_at IS NULL').fetchone()[0], 0)

    def test_rate_limits_survive_requests_and_dont_lock_login(self):
        from password_reset import reserve_reset_request
        self.assertEqual(reserve_reset_request('admin@example.com', '192.0.2.1'), 'admin@example.com')
        self.assertIsNone(reserve_reset_request('admin@example.com', '192.0.2.2'))
        self.assertIsNotNone(authenticate_user('admin', 'PreviousPassword123!'))
        for i in range(29):
            reserve_reset_request('unknown'+str(i)+'@example.com', '192.0.2.1')
        self.assertIsNone(reserve_reset_request('other@example.com', '192.0.2.1'))
        with db.connect() as con:
            self.assertNotIn('admin@example.com', [r[0] for r in con.execute('SELECT request_key FROM staff_reset_requests')])

    def test_email_is_unique_and_validated_and_old_client_keeps_it(self):
        with self.assertRaises(ValueError):
            create_user('duplicate', 'PreviousPassword123!', email=' ADMIN@EXAMPLE.COM ')
        with self.assertRaises(ValueError):
            update_user(self.uid, email='bad\r\nBcc:other@example.com')
        update_user(self.uid, display_name='نام جدید')
        with db.connect() as con:
            self.assertEqual(con.execute('SELECT email FROM staff_users WHERE id=?', (self.uid,)).fetchone()[0], 'admin@example.com')

    def test_weak_and_same_password_do_not_consume_valid_link(self):
        from password_reset import reset_password
        token = self.issue()
        for password in ('short', 'PreviousPassword123!'):
            with self.assertRaises(ValueError):
                reset_password(token, password)
        reset_password(token, 'ReplacementPassword123!')

    def test_api_is_non_enumerating_and_never_returns_token(self):
        from fastapi.testclient import TestClient
        from main import app
        links = []
        with TestClient(app) as client, patch('password_reset.send_reset_email', side_effect=lambda recipient, link: links.append(link)):
            known = client.post('/api/auth/forgot-password', json={'email': 'admin@example.com'}, headers={'Host':'evil.example'})
            unknown = client.post('/api/auth/forgot-password', json={'email': 'unknown@example.com'})
        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.json(), unknown.json())
        self.assertNotIn('token', known.text)
        self.assertTrue(links[0].startswith('https://market.example.com/reset-password#token='))

    def test_no_config_is_explicitly_unavailable_for_every_email(self):
        from fastapi.testclient import TestClient
        from main import app
        with patch.dict(os.environ, {'SATNO_SMTP_PASSWORD': ''}), TestClient(app) as client:
            self.assertFalse(client.get('/api/auth/recovery-status').json()['enabled'])
            for email in ('admin@example.com', 'unknown@example.com'):
                self.assertEqual(client.post('/api/auth/forgot-password', json={'email':email}).status_code, 503)

    def test_unknown_token_does_not_trigger_expensive_password_hash(self):
        from password_reset import reset_password
        with patch('password_reset.hash_password') as hashing:
            with self.assertRaises(ValueError):
                reset_password('x' * 43, 'ReplacementPassword123!')
            hashing.assert_not_called()

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL needed for loopback TLS fixture")
    def test_real_starttls_smtp_delivery_and_reset(self):
        import re
        from tests.smtp_fixture import TLSInbox
        from password_reset import deliver_reset_email, reset_password
        with TLSInbox() as inbox, patch.dict(os.environ, inbox.settings):
            deliver_reset_email('admin@example.com')
            mail = inbox.messages.get(timeout=5)
            self.assertEqual(str(mail['To']), 'admin@example.com')
            self.assertEqual(str(mail['From']), 'fixture@example.com')
            link = re.search(r'https://\S+', mail.get_content()).group()
            token = parse_qs(urlsplit(link).fragment)['token'][0]
            reset_password(token, 'ReplacementPassword123!')
            self.assertIsNotNone(authenticate_user('admin', 'ReplacementPassword123!'))

    def test_unsafe_public_url_and_plain_smtp_are_unavailable(self):
        from recovery_mailer import recovery_settings, RecoveryUnavailable
        for change in ({'SATNO_PUBLIC_BASE_URL': 'https://user:pass@example.com'},
                       {'SATNO_PUBLIC_BASE_URL': 'http://market.example.com', 'SATNO_RECOVERY_ALLOW_HTTP': '0'},
                       {'SATNO_SMTP_SECURITY': 'plain'}, {'SATNO_PUBLIC_BASE_URL': 'https://market.example.com:bad'}):
            with self.subTest(change=change), patch.dict(os.environ, change):
                with self.assertRaises(RecoveryUnavailable):
                    recovery_settings()

    def test_email_management_requires_admin_and_does_not_leak_to_viewer(self):
        from fastapi.testclient import TestClient
        from main import app
        create_user('viewer', 'PreviousPassword123!', 'viewer', email='viewer@example.com')
        with TestClient(app) as client:
            client.post('/api/auth/login', json={'username':'viewer', 'password':'PreviousPassword123!'})
            self.assertEqual(client.get('/api/admin/users').status_code, 403)
            self.assertEqual(client.patch('/api/admin/users/'+str(self.uid), json={'email':'changed@example.com'}).status_code, 403)
            client.post('/api/auth/logout')
            client.post('/api/auth/login', json={'username':'admin', 'password':'PreviousPassword123!'})
            result=client.patch('/api/admin/users/'+str(self.uid), json={'email':'changed@example.com'})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['email'], 'changed@example.com')
            client.patch('/api/admin/users/'+str(self.uid), json={'display_name':'نام جدید'})
            self.assertEqual(client.get('/api/admin/users').json()[0]['email'], 'changed@example.com')

    def test_additive_migration_preserves_existing_user_password_and_session(self):
        session = create_session(self.uid)
        with db.connect() as con:
            before = con.execute('SELECT password_hash FROM staff_users WHERE id=?',(self.uid,)).fetchone()[0]
            con.execute('DROP INDEX idx_staff_users_email')
            con.execute('ALTER TABLE staff_users DROP COLUMN email')
        db.init_db()
        db.init_db()
        with db.connect() as con:
            after = con.execute('SELECT password_hash,email FROM staff_users WHERE id=?',(self.uid,)).fetchone()
        self.assertEqual(after['password_hash'], before)
        self.assertIsNone(after['email'])
        self.assertIsNotNone(resolve_session(session))

    def test_login_cannot_create_old_password_session_after_concurrent_reset(self):
        from fastapi.testclient import TestClient
        from main import app
        from auth import verify_password
        from password_reset import reset_password
        token = self.issue()
        triggered = []
        def interleaved(password, encoded):
            valid = verify_password(password, encoded)
            if password == 'PreviousPassword123!' and not triggered:
                triggered.append(True)
                reset_password(token, 'ReplacementPassword123!')
            return valid
        with TestClient(app) as client, patch('auth.verify_password', side_effect=interleaved):
            response = client.post('/api/auth/login', json={'username':'admin','password':'PreviousPassword123!'})
        self.assertEqual(response.status_code, 401)
        with db.connect() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM staff_sessions WHERE revoked_at IS NULL').fetchone()[0], 0)

    def test_concurrent_token_consumption_succeeds_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from password_reset import reset_password
        token = self.issue()
        def attempt(number):
            try:
                reset_password(token, 'ConcurrentNewPassword123!'+str(number))
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sorted(executor.map(attempt, (1,2))), [False,True])

    def test_concurrent_rate_reservation_does_not_duplicate_delivery_slots(self):
        from concurrent.futures import ThreadPoolExecutor
        from password_reset import reserve_reset_request
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda n:reserve_reset_request('admin@example.com','192.0.2.'+str(n)), (1,2)))
        self.assertEqual(sum(item is not None for item in results), 1)

    def test_own_password_change_and_recovery_cannot_both_consume_old_credentials(self):
        import threading
        from auth import verify_password
        from password_reset import reset_password
        token = self.issue()
        results = []
        workers = []
        def recovery():
            try:
                reset_password(token, 'ReplacementPassword123!')
                results.append(True)
            except ValueError:
                results.append(False)
        def interleaved(password, encoded):
            valid = verify_password(password, encoded)
            if password == 'PreviousPassword123!' and not workers:
                worker = threading.Thread(target=recovery)
                workers.append(worker)
                worker.start()
                worker.join(timeout=.5)
            return valid
        with patch('auth.verify_password', side_effect=interleaved):
            results.append(change_own_password(self.uid, 'PreviousPassword123!', 'OwnChangedPassword123!'))
        for worker in workers:
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
        self.assertEqual(sorted(results), [False, True])

    def test_smtp_never_authenticates_without_successful_tls(self):
        import smtplib
        from recovery_mailer import send_reset_email
        with patch('recovery_mailer.smtplib.SMTP') as smtp:
            transport = smtp.return_value.__enter__.return_value
            transport.starttls.side_effect = smtplib.SMTPNotSupportedError('TLS unavailable')
            with self.assertRaises(smtplib.SMTPNotSupportedError):
                send_reset_email('admin@example.com', 'https://market.example.com/reset-password#token=synthetic')
            transport.login.assert_not_called()

    def test_ssl_mode_requires_verified_certificate_context(self):
        import ssl
        from recovery_mailer import send_reset_email
        with patch.dict(os.environ, {'SATNO_SMTP_SECURITY':'ssl','SATNO_SMTP_PORT':'465'}):
            with patch('recovery_mailer.smtplib.SMTP_SSL') as smtp:
                send_reset_email('admin@example.com', 'https://market.example.com/reset-password#token=synthetic')
                context = smtp.call_args.kwargs['context']
                self.assertTrue(context.check_hostname)
                self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
                smtp.return_value.__enter__.return_value.send_message.assert_called_once()

    def test_admin_email_tool_is_read_only_by_default_and_uses_explicit_database(self):
        import hashlib
        import subprocess
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        before = hashlib.sha256(Path(db.DB_PATH).read_bytes()).hexdigest()
        wrong = str(Path(self.tmp.name)/'wrong.db')
        command = [sys.executable, str(root/'tools/set_admin_email.py'), '--database', db.DB_PATH,
                   '--email', 'operator@example.com']
        result = subprocess.run(command, cwd=root, env={**os.environ,'DATABASE_PATH':wrong}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('READ_ONLY', result.stdout)
        self.assertEqual(hashlib.sha256(Path(db.DB_PATH).read_bytes()).hexdigest(), before)
        applied = subprocess.run(command+['--apply'], cwd=root, env={**os.environ,'DATABASE_PATH':wrong}, capture_output=True, text=True)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertFalse(Path(wrong).exists())
        self.assertIsNotNone(authenticate_user('admin', 'PreviousPassword123!'))
        with db.connect() as con:
            self.assertEqual(con.execute('SELECT email FROM staff_users WHERE id=?',(self.uid,)).fetchone()[0], 'operator@example.com')

    def test_admin_email_tool_refuses_ambiguous_administrator_selection(self):
        import subprocess
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        create_user('another-admin', 'PreviousPassword123!', 'admin', email='other@example.com')
        command = [sys.executable, str(root/'tools/set_admin_email.py'), '--database', db.DB_PATH,
                   '--email', 'operator@example.com', '--apply']
        rejected = subprocess.run(command, cwd=root, capture_output=True, text=True)
        self.assertNotEqual(rejected.returncode, 0)
        selected = subprocess.run(command+['--username','admin'], cwd=root, capture_output=True, text=True)
        self.assertEqual(selected.returncode, 0, selected.stderr)
        with db.connect() as con:
            rows = dict(con.execute('SELECT username,email FROM staff_users').fetchall())
        self.assertEqual(rows, {'admin':'operator@example.com','another-admin':'other@example.com'})
