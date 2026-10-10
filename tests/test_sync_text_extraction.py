import unittest
from types import SimpleNamespace

from sync_bale import get_text


class SyncTextExtractionTests(unittest.TestCase):
    def test_extracts_plain_text(self):
        message = SimpleNamespace(content=SimpleNamespace(text="  فروش پنل  "))
        self.assertEqual(get_text(message), "فروش پنل")

    def test_extracts_media_caption_when_text_is_empty(self):
        message = SimpleNamespace(
            content=SimpleNamespace(
                text=None,
                media=SimpleNamespace(caption="  اینورتر Growatt 25kW  "),
            )
        )
        self.assertEqual(get_text(message), "اینورتر Growatt 25kW")

    def test_empty_media_is_ignored(self):
        message = SimpleNamespace(
            content=SimpleNamespace(text=None, media=SimpleNamespace(caption=None))
        )
        self.assertIsNone(get_text(message))


if __name__ == "__main__":
    unittest.main()
