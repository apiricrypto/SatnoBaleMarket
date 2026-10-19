import os
import tempfile
import unittest
import warnings
import getpass
from unittest.mock import patch

from fastapi.testclient import TestClient
import db
import auth
from main import app


class PasswordRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = db.DB_PATH
        db.DB_PATH = os.path.join(self.tmp.name, 'recovery.db')
        auth.create_user('owner', 'OriginalPassword123!', 'admin')
        auth.create_user('member', 'OriginalPassword123!', 'viewer')
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        db.DB_PATH = self.previous
        self.tmp.cleanup()

    def login(self, username):
        return self.client.post('/api/auth/login', json={
            'username': username, 'password': 'OriginalPassword123!'})

    def test_public_request_is_generic_deduplicated_and_does_not_change_password(self):
        responses = [self.client.post('/api/auth/forgot-password', json={'username': name})
                     for name in (' MEMBER ', 'missing', 'member')]
        self.assertEqual([r.status_code for r in responses], [202, 202, 202])
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertIsNotNone(auth.authenticate_user('member', 'OriginalPassword123!'))
        self.login('owner')
        pending = self.client.get('/api/admin/password-reset-requests').json()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]['username'], 'member')
        self.assertNotIn('password_hash', pending[0])

    def test_requests_are_admin_only_and_password_reset_resolves_them(self):
        self.client.post('/api/auth/forgot-password', json={'username': 'member'})
        self.assertEqual(self.client.get('/api/admin/password-reset-requests').status_code, 401)
        self.login('member')
        self.assertEqual(self.client.get('/api/admin/password-reset-requests').status_code, 403)
        member = auth.authenticate_user('member', 'OriginalPassword123!')
        token = auth.create_session(member['id'])
        self.login('owner')
        result = self.client.patch('/api/admin/users/' + str(member['id']),
                                   json={'password': 'ReplacementPassword123!'})
        self.assertEqual(result.status_code, 200)
        self.assertIsNone(auth.resolve_session(token))
        self.assertEqual(self.client.get('/api/admin/password-reset-requests').json(), [])

    def test_inactive_accounts_do_not_create_requests(self):
        member = auth.authenticate_user('member', 'OriginalPassword123!')
        auth.update_user(member['id'], is_active=False)
        self.assertEqual(self.client.post('/api/auth/forgot-password',
                                         json={'username': 'member'}).status_code, 202)
        self.login('owner')
        self.assertEqual(self.client.get('/api/admin/password-reset-requests').json(), [])

    def test_emergency_admin_recovery_revokes_sessions_and_preserves_role(self):
        import reset_admin_password
        owner = auth.authenticate_user('owner', 'OriginalPassword123!')
        token = auth.create_session(owner['id'])
        with patch('getpass.getpass', side_effect=['ReplacementPassword123!'] * 2):
            reset_admin_password.main(['owner', '--database', db.DB_PATH])
        self.assertIsNone(auth.resolve_session(token))
        self.assertIsNone(auth.authenticate_user('owner', 'OriginalPassword123!'))
        self.assertEqual(auth.authenticate_user('owner', 'ReplacementPassword123!')['role'], 'admin')

    def test_emergency_recovery_rejects_non_admin_missing_db_and_mismatched_passwords(self):
        import reset_admin_password
        for username, path, passwords in [
            ('member', db.DB_PATH, ['ReplacementPassword123!'] * 2),
            ('owner', db.DB_PATH, ['ReplacementPassword123!', 'different']),
            ('owner', os.path.join(self.tmp.name, 'missing.db'), []),
        ]:
            with self.subTest(username=username, path=path), patch('getpass.getpass', side_effect=passwords):
                with self.assertRaises(SystemExit):
                    reset_admin_password.main([username, '--database', path])
        self.assertIsNotNone(auth.authenticate_user('owner', 'OriginalPassword123!'))

    def test_login_exposes_recovery_form_and_admin_panel_exposes_pending_requests(self):
        page = self.client.get('/login').text
        self.assertIn('id="forgotForm"', page)
        self.assertIn('/api/auth/forgot-password', page)
        self.login('owner')
        self.assertIn('/api/admin/password-reset-requests', self.client.get('/admin/users').text)

    def test_emergency_recovery_stops_when_password_cannot_be_hidden(self):
        import reset_admin_password

        def insecure_terminal(*args):
            warnings.warn('Can not control echo on the terminal.', getpass.GetPassWarning)
            return 'ReplacementPassword123!'

        with patch('getpass.getpass', side_effect=insecure_terminal):
            with self.assertRaises(SystemExit):
                reset_admin_password.main(['owner', '--database', db.DB_PATH])
        self.assertIsNotNone(auth.authenticate_user('owner', 'OriginalPassword123!'))
