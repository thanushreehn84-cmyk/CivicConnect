
"""
Civic Connect - Complaint Summarizer

Creates a concise, structured summary of a citizen's complaint.
This is an extractive, rule-based summarizer, not a generative AI model.
"""

import re


def clean_text(text):
    """Clean and normalize complaint text."""
    if not isinstance(text, str):
        return ""

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_sentences(text):
    """Split text into individual sentences."""
    if not text:
        return []

    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def summarize_complaint(description, max_sentences=3):
    """
    Generate a short summary from the original complaint.

    Selects the most informative sentences while preserving
    their original wording.
    """
    description = clean_text(description)

    if not description:
        return {
            "summary": "No complaint description provided.",
            "original_length": 0,
            "summary_length": 0,
            "compression_ratio": 0.0,
            "method": "extractive_rule_based"
        }

    if not isinstance(max_sentences, int) or max_sentences < 1:
        raise ValueError("max_sentences must be a positive integer.")

    sentences = split_sentences(description)

    if len(sentences) <= max_sentences:
        summary = description
    else:
        # Prefer longer, information-rich sentences.
        ranked = sorted(
            enumerate(sentences),
            key=lambda item: len(item[1].split()),
            reverse=True
        )

        selected_indices = sorted(
            index for index, _ in ranked[:max_sentences]
        )

        summary = " ".join(
            sentences[index] for index in selected_indices
        )

    original_length = len(description)
    summary_length = len(summary)

    compression_ratio = (
        round(1 - summary_length / original_length, 3)
        if original_length else 0.0
    )

    return {
        "summary": summary,
        "original_length": original_length,
        "summary_length": summary_length,
        "compression_ratio": compression_ratio,
        "method": "extractive_rule_based"
    }


def build_complaint_brief(complaint):
    """
    Create a structured brief for administrators and departments.

    Expected dictionary keys:
        complaint_id, category, location, description, status
    """
    if not isinstance(complaint, dict):
        raise TypeError("complaint must be a dictionary.")

    description = complaint.get("description", "")

    summary_result = summarize_complaint(description)

    return {
        "complaint_id": complaint.get("complaint_id", "Not available"),
        "category": complaint.get("category", "Not specified"),
        "location": complaint.get("location", "Not specified"),
        "status": complaint.get("status", "Not specified"),
        "summary": summary_result["summary"]
    }
