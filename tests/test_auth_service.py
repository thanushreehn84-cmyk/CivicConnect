
"""
Civic Connect - Authentication Service Tests
"""

import unittest

from services.auth_service import create_staff_account


class TestAuthenticationService(unittest.TestCase):

    def test_invalid_role_is_rejected(self):
        with self.assertRaises(ValueError):
            create_staff_account(
                username="testuser",
                password="StrongPassword123!",
                role="unknown",
            )

    def test_short_password_is_rejected(self):
        with self.assertRaises(ValueError):
            create_staff_account(
                username="testuser",
                password="short",
                role="validator",
            )

    def test_empty_username_is_rejected(self):
        with self.assertRaises(ValueError):
            create_staff_account(
                username="",
                password="StrongPassword123!",
                role="validator",
            )


if __name__ == "__main__":
    unittest.main()
