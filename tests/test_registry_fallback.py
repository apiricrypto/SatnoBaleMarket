import unittest

from sync_bale import registry_row_to_target


class RegistryFallbackTests(unittest.TestCase):
    def test_channel_registry_row_becomes_peer(self):
        target = registry_row_to_target({
            "source_key": "bale:2:123",
            "title": "Solar Market",
            "peer_type": "2",
            "peer_id": "123",
        })
        self.assertIsNotNone(target)
        self.assertEqual(target.title, "Solar Market")
        self.assertEqual(target.peer.type, 2)
        self.assertEqual(target.peer.id, 123)

    def test_user_registry_row_becomes_peer(self):
        target = registry_row_to_target({
            "source_key": "bale:1:456",
            "title": None,
            "peer_type": 1,
            "peer_id": 456,
        })
        self.assertEqual(target.title, "bale:1:456")
        self.assertEqual(target.peer.type, 1)
        self.assertEqual(target.peer.id, 456)

    def test_invalid_registry_row_is_skipped(self):
        target = registry_row_to_target({
            "source_key": "bad",
            "title": "bad",
            "peer_type": "channel",
            "peer_id": "not-a-number",
        })
        self.assertIsNone(target)


if __name__ == "__main__":
    unittest.main()
