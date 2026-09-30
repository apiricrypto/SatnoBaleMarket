import unittest
from backfill_engine import next_budget,should_complete

class BackfillEngineTests(unittest.TestCase):
    def test_budget(self):
        self.assertEqual(next_budget(250,1000),750)
        self.assertEqual(next_budget(1000,1000),0)
    def test_short_batch_marks_end(self):
        self.assertTrue(should_complete(40,100))
        self.assertFalse(should_complete(100,100))

if __name__=="__main__":
    unittest.main()
