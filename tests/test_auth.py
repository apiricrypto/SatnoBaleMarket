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
    list_users,
    update_user,
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


    def test_user_management(self):
        create_user("admin1", "StrongPassword123!", role="admin", display_name="Admin")
        create_user("sales1", "StrongPassword123!", role="sales", display_name="Sales")
        users = list_users()
        self.assertEqual(len(users), 2)
        self.assertNotIn("password_hash", users[0])

        sales = next(u for u in users if u["username"] == "sales1")
        user = authenticate_user("sales1", "StrongPassword123!")
        token = create_session(user["id"])
        updated = update_user(sales["id"], role="viewer", display_name="Viewer")
        self.assertEqual(updated["role"], "viewer")
        self.assertEqual(updated["display_name"], "Viewer")
        self.assertIsNone(resolve_session(token))

        update_user(sales["id"], password="NewStrongPassword123!")
        self.assertIsNone(authenticate_user("sales1", "StrongPassword123!"))
        self.assertIsNotNone(authenticate_user("sales1", "NewStrongPassword123!"))

        update_user(sales["id"], is_active=False)
        self.assertIsNone(authenticate_user("sales1", "NewStrongPassword123!"))

    def test_last_active_admin_is_protected(self):
        create_user("admin1", "StrongPassword123!", role="admin")
        admin = list_users()[0]
        with self.assertRaises(ValueError):
            update_user(admin["id"], role="viewer")
        with self.assertRaises(ValueError):
            update_user(admin["id"], is_active=False)

if __name__ == "__main__":
    unittest.main()
