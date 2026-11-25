
"""
Civic Connect - Validation Service Tests
"""

import unittest
from unittest.mock import patch, MagicMock

from services.validation_service import (
    calculate_suspicion_score,
    update_validation_decision,
)


class TestSuspicionScore(unittest.TestCase):

    def test_normal_complaint(self):
        result = calculate_suspicion_score()

        self.assertEqual(result["suspicion_score"], 0)
        self.assertEqual(result["status"], "Assigned")

    def test_duplicate_complaint(self):
        result = calculate_suspicion_score(duplicate=True)

        self.assertEqual(result["suspicion_score"], 50)
        self.assertEqual(result["status"], "Flagged for Review")

    def test_spam_complaint(self):
        result = calculate_suspicion_score(spam=True)

        self.assertEqual(result["suspicion_score"], 40)

    def test_suspicion_score_is_capped_at_100(self):
        result = calculate_suspicion_score(
            duplicate=True,
            spam=True,
            has_evidence=False,
        )

        self.assertEqual(result["suspicion_score"], 100)

    def test_validation_message_is_returned(self):
        result = calculate_suspicion_score(duplicate=True)

        self.assertTrue(result["validation_message"])


class TestValidationDecision(unittest.TestCase):

    @patch("services.validation_service.add_history")
    @patch("services.validation_service.get_db_connection")
    def test_approve_complaint(self, mock_connection, mock_history):
        connection = MagicMock()
        mock_connection.return_value = connection

        cursor = MagicMock()
        cursor.rowcount = 1
        connection.execute.return_value = cursor

        result = update_validation_decision(
            "CC001",
            "approve",
            validator="Test Validator",
        )

        self.assertTrue(result)
        connection.commit.assert_called_once()
        mock_history.assert_called_once()

    @patch("services.validation_service.get_db_connection")
    def test_invalid_decision(self, mock_connection):
        with self.assertRaises(ValueError):
            update_validation_decision(
                "CC001",
                "unknown",
            )

        mock_connection.assert_not_called()

    @patch("services.validation_service.get_db_connection")
    def test_missing_complaint_id(self, mock_connection):
        with self.assertRaises(ValueError):
            update_validation_decision("", "approve")

        mock_connection.assert_not_called()


if __name__ == "__main__":
    unittest.main()
