import unittest
from fastapi.testclient import TestClient
import tempfile
import os
import db
from main import app
from auth import create_user


class StaffInterfaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = db.DB_PATH
        db.DB_PATH = os.path.join(self.tmp.name, "ui.db")
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        db.DB_PATH = self.previous
        self.tmp.cleanup()

    def login(self, role):
        create_user(role, "InitialPassword123!", role)
        self.assertEqual(
            self.client.post(
                "/api/auth/login",
                json={"username": role, "password": "InitialPassword123!"},
            ).status_code,
            200,
        )

    def test_navigation_matches_role_and_password_is_always_reachable(self):
        for role in ("viewer", "sales", "admin"):
            with self.subTest(role=role):
                self.login(role)
                for path in ("/", "/status", "/profile/password"):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('aria-label="ناوبری اصلی"', response.text)
                    self.assertIn('href="/profile/password"', response.text)
                    self.assertIn("data-staff-logout", response.text)
                    self.assertEqual(
                        'href="/admin/users"' in response.text, role == "admin"
                    )
                    self.assertEqual(
                        'href="/review"' in response.text, role != "viewer"
                    )
                self.client.post("/api/auth/logout")

    def test_password_change_clears_cookie_and_rejects_old_password(self):
        self.login("sales")
        response = self.client.post(
            "/api/auth/change-password",
            json={
                "current_password": "InitialPassword123!",
                "new_password": "ChangedPassword123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("satno_staff_session", self.client.cookies)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        for password, expected in [
            ("InitialPassword123!", 401),
            ("ChangedPassword123!", 200),
        ]:
            self.assertEqual(
                self.client.post(
                    "/api/auth/login", json={"username": "sales", "password": password}
                ).status_code,
                expected,
            )
