
"""
Civic Connect - AI Module Tests

Tests classification, duplicate detection,
priority prediction, and complaint summarization.
"""

import unittest

from ai.classifier import classify_complaint
from ai.duplicate_detector import (
    text_similarity,
    compare_complaints,
    find_duplicate_complaints,
)
from ai.priority_predictor import predict_priority
from ai.summarizer import (
    summarize_complaint,
    build_complaint_brief,
)


class TestComplaintClassifier(unittest.TestCase):

    def test_classifier_returns_expected_fields(self):
        result = classify_complaint(
            "There is illegal construction happening in my area."
        )

        self.assertIsInstance(result, dict)
        self.assertIn("category", result)
        self.assertIn("confidence", result)
        self.assertIn("scores", result)
        self.assertIn("method", result)

    def test_classifier_confidence_is_valid(self):
        result = classify_complaint(
            "There is a problem in my neighbourhood."
        )

        self.assertGreaterEqual(result["confidence"], 0)
        self.assertLessEqual(result["confidence"], 1)


class TestDuplicateDetection(unittest.TestCase):

    def test_identical_text_has_full_similarity(self):
        text = "Garbage is being dumped near the public road."

        similarity = text_similarity(text, text)

        self.assertAlmostEqual(similarity, 1.0, places=2)

    def test_identical_complaints_are_possible_duplicates(self):
        complaint = {
            "description": "Garbage is dumped near the public road.",
            "location": "Main Road",
            "category": "Environmental Issue",
        }

        result = compare_complaints(complaint, complaint)

        self.assertIsInstance(result, dict)
        self.assertIn("similarity", result)
        self.assertIn("is_duplicate", result)
        self.assertTrue(result["is_duplicate"])

    def test_duplicate_search_returns_matches(self):
        new_complaint = {
            "description": "Garbage is dumped near the public road.",
            "location": "Main Road",
            "category": "Environmental Issue",
        }

        existing_complaints = [
            {
                "complaint_id": "CC001",
                "description": "Garbage is dumped near the public road.",
                "location": "Main Road",
                "category": "Environmental Issue",
            }
        ]

        results = find_duplicate_complaints(
            new_complaint,
            existing_complaints,
        )

        self.assertIsInstance(results, list)
        self.assertGreaterEqual(len(results), 1)


class TestPriorityPrediction(unittest.TestCase):

    def test_priority_prediction_returns_expected_fields(self):
        result = predict_priority(
            "There is a dangerous situation near the public road.",
            category="Public Safety",
            location="Main Road",
        )

        self.assertIsInstance(result, dict)
        self.assertIn("priority", result)
        self.assertIn("score", result)
        self.assertIn("explanation", result)

    def test_priority_score_is_within_range(self):
        result = predict_priority(
            "A public safety issue has been reported."
        )

        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)


class TestComplaintSummarizer(unittest.TestCase):

    def test_summarizer_returns_expected_fields(self):
        description = (
            "Garbage has been dumped near the public road. "
            "The area has become dirty. "
            "Residents are facing difficulties because of the waste."
        )

        result = summarize_complaint(description)

        self.assertIsInstance(result, dict)
        self.assertIn("summary", result)
        self.assertIn("original_length", result)
        self.assertIn("summary_length", result)

    def test_summary_is_not_longer_than_original(self):
        description = (
            "Garbage has been dumped near the public road. "
            "Residents are facing difficulties."
        )

        result = summarize_complaint(description)

        self.assertLessEqual(
            result["summary_length"],
            result["original_length"],
        )

    def test_complaint_brief_contains_summary(self):
        complaint = {
            "complaint_id": "CC001",
            "category": "Environmental Issue",
            "location": "Main Road",
            "status": "Assigned",
            "description": "Garbage is dumped near the public road.",
        }

        result = build_complaint_brief(complaint)

        self.assertIn("complaint_id", result)
        self.assertIn("summary", result)


if __name__ == "__main__":
    unittest.main()
