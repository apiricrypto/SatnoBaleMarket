import unittest
from backfill_engine import next_budget,should_complete

class BackfillEngineTests(unittest.TestCase):
    def test_budget(self):
        self.assertEqual(next_budget(250,1000),750)
        self.assertEqual(next_budget(1000,1000),0)
    def test_short_batch_does_not_mark_end(self):
        self.assertFalse(should_complete(40,100,40,1000))
        self.assertFalse(should_complete(0,100,0,1000))
    def test_target_marks_complete(self):
        self.assertTrue(should_complete(100,100,1000,1000))

if __name__=="__main__":
    unittest.main()
