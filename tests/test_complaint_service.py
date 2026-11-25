
"""
Civic Connect - Complaint Service Tests
"""

import unittest

from services.complaint_service import (
    validate_date,
    validate_location,
    validate_description,
    is_spam,
)


class TestComplaintValidation(unittest.TestCase):

    def test_valid_date(self):
        result = validate_date("2026-11-24")
        self.assertTrue(result)

    def test_invalid_date(self):
        result = validate_date("invalid-date")
        self.assertFalse(result)

    def test_empty_location(self):
        result = validate_location("")
        self.assertFalse(result)

    def test_valid_location(self):
        result = validate_location("Bengaluru")
        self.assertTrue(result)

    def test_empty_description(self):
        result = validate_description("")
        self.assertFalse(result)

    def test_valid_description(self):
        result = validate_description(
            "Garbage has been dumped near the public road."
        )
        self.assertTrue(result)

    def test_spam_detection_returns_boolean(self):
        result = is_spam(
            "Garbage is being dumped repeatedly near the road."
        )
        self.assertIsInstance(result, bool)


if __name__ == "__main__":
    unittest.main()

