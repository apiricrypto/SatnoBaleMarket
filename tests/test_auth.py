import unittest
from auth import hash_password,verify_password

class AuthTests(unittest.TestCase):
    def test_password_round_trip(self):
        encoded=hash_password("StrongPassword123!")
        self.assertTrue(verify_password("StrongPassword123!",encoded))
        self.assertFalse(verify_password("wrong",encoded))
    def test_salts_are_unique(self):
        self.assertNotEqual(hash_password("same-password"),hash_password("same-password"))

if __name__=="__main__":
    unittest.main()
