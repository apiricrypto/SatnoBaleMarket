import unittest

from main import health, satno_ui_css
from ui_theme import SATNO_UI_CSS


class UIThemeTests(unittest.TestCase):
    def test_health_reports_ui_refresh_version(self):
        self.assertEqual(health()["version"], "0.5.1")

    def test_shared_css_contains_core_staff_components(self):
        for token in (
            "--satno-primary",
            ".metric-grid",
            ".result-card",
            ".source",
            ".empty-state",
            ".nav",
        ):
            self.assertIn(token, SATNO_UI_CSS)

    def test_css_endpoint_returns_stylesheet(self):
        response = satno_ui_css()
        self.assertEqual(response.media_type, "text/css; charset=utf-8")
        self.assertIn(b"--satno-primary", response.body)


if __name__ == "__main__":
    unittest.main()
