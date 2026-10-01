import os
import tempfile
import unittest

import db
from auth import (
    authenticate_user,
    create_session,
    create_user,
    hash_password,
    resolve_session,
    revoke_session,
    role_allows,
    verify_password,
)


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.DB_PATH = os.path.join(self.tmp.name, "auth-test.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_password_round_trip(self):
        encoded = hash_password("StrongPassword123!")
        self.assertTrue(verify_password("StrongPassword123!", encoded))
        self.assertFalse(verify_password("wrong", encoded))

    def test_salts_are_unique(self):
        self.assertNotEqual(
            hash_password("same-password"),
            hash_password("same-password"),
        )

    def test_login_session_logout_lifecycle(self):
        create_user("Sales.User", "StrongPassword123!", role="sales", display_name="Sales User")

        user = authenticate_user("sales.user", "StrongPassword123!")
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "sales")
        self.assertIsNone(authenticate_user("sales.user", "wrong-password"))

        token = create_session(user["id"])
        self.assertTrue(token)
        self.assertEqual(resolve_session(token)["username"], "sales.user")

        with db.connect() as con:
            row = con.execute("SELECT token_hash FROM staff_sessions").fetchone()
        self.assertNotEqual(row["token_hash"], token)
        self.assertEqual(len(row["token_hash"]), 64)

        self.assertTrue(revoke_session(token))
        self.assertIsNone(resolve_session(token))

    def test_inactive_user_invalidates_session(self):
        create_user("viewer1", "StrongPassword123!", role="viewer")
        user = authenticate_user("viewer1", "StrongPassword123!")
        token = create_session(user["id"])

        with db.connect() as con:
            con.execute("UPDATE staff_users SET is_active=0 WHERE id=?", (user["id"],))

        self.assertIsNone(resolve_session(token))

    def test_role_permissions(self):
        self.assertTrue(role_allows("viewer", "read"))
        self.assertFalse(role_allows("viewer", "lead:send"))
        self.assertTrue(role_allows("sales", "lead:send"))
        self.assertFalse(role_allows("sales", "users:manage"))
        self.assertTrue(role_allows("admin", "users:manage"))
        self.assertTrue(role_allows("admin", "message:write"))


if __name__ == "__main__":
    unittest.main()
