
"""
Civic Connect - AI Duplicate Complaint Detector

Detects potentially duplicate civic complaints by comparing:
1. Complaint descriptions
2. Complaint locations
3. Complaint categories

Uses text similarity and rule-based matching.
"""

import re
from difflib import SequenceMatcher


def normalize_text(text):
    """Convert text into a normalized format for comparison."""

    if not isinstance(text, str):
        return ""

    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text


def text_similarity(text1, text2):
    """Calculate similarity between two text values."""

    first = normalize_text(text1)
    second = normalize_text(text2)

    if not first or not second:
        return 0.0

    if first == second:
        return 1.0

    return SequenceMatcher(
        None,
        first,
        second
    ).ratio()


def location_similarity(location1, location2):
    """Calculate similarity between two complaint locations."""

    first = normalize_text(location1)
    second = normalize_text(location2)

    if not first or not second:
        return 0.0

    if first == second:
        return 1.0

    return SequenceMatcher(
        None,
        first,
        second
    ).ratio()


def compare_complaints(
    new_complaint,
    existing_complaint
):
    """
    Compare two complaints and determine whether
    they may represent the same civic issue.
    """

    if not isinstance(new_complaint, dict):
        raise ValueError("New complaint must be a dictionary.")

    if not isinstance(existing_complaint, dict):
        raise ValueError("Existing complaint must be a dictionary.")

    new_description = new_complaint.get("description", "")
    existing_description = existing_complaint.get("description", "")

    new_location = new_complaint.get("location", "")
    existing_location = existing_complaint.get("location", "")

    new_category = normalize_text(
        new_complaint.get("category", "")
    )

    existing_category = normalize_text(
        existing_complaint.get("category", "")
    )

    # Calculate individual similarity scores.
    description_score = text_similarity(
        new_description,
        existing_description
    )

    location_score = location_similarity(
        new_location,
        existing_location
    )

    category_match = (
        bool(new_category)
        and bool(existing_category)
        and new_category == existing_category
    )

    category_score = 1.0 if category_match else 0.0

    # Weighted similarity calculation.
    similarity = (
        description_score * 0.65
        + location_score * 0.25
        + category_score * 0.10
    )

    similarity = round(similarity, 4)

    # Duplicate threshold.
    is_possible_duplicate = similarity >= 0.75

    if similarity >= 0.90:
        recommendation = "Very high similarity - manual review required"
    elif similarity >= 0.75:
        recommendation = "Review possible duplicate"
    elif similarity >= 0.50:
        recommendation = "Some similarity detected"
    else:
        recommendation = "No significant similarity detected"

    return {
        "similarity": similarity,
        "description_similarity": round(description_score, 4),
        "location_similarity": round(location_score, 4),
        "category_match": category_match,

        # Both keys are provided for compatibility.
        "is_possible_duplicate": is_possible_duplicate,
        "is_duplicate": is_possible_duplicate,

        "recommendation": recommendation,
    }


def find_duplicate_complaints(
    new_complaint,
    existing_complaints,
    threshold=0.75
):
    """
    Find possible duplicates from a list of existing complaints.

    Returns matching complaints sorted by similarity,
    from highest to lowest.
    """

    if not isinstance(new_complaint, dict):
        raise ValueError("New complaint must be a dictionary.")

    if not isinstance(existing_complaints, (list, tuple)):
        raise ValueError("Existing complaints must be a list.")

    if not isinstance(threshold, (int, float)):
        raise ValueError("Threshold must be a number.")

    if not 0 <= threshold <= 1:
        raise ValueError("Threshold must be between 0 and 1.")

    duplicate_matches = []

    for existing_complaint in existing_complaints:

        if not isinstance(existing_complaint, dict):
            continue

        result = compare_complaints(
            new_complaint,
            existing_complaint
        )

        if result["similarity"] >= threshold:

            duplicate_matches.append({
                "complaint": existing_complaint,
                "similarity": result["similarity"],
                "description_similarity": result[
                    "description_similarity"
                ],
                "location_similarity": result[
                    "location_similarity"
                ],
                "category_match": result["category_match"],
                "is_possible_duplicate": result[
                    "is_possible_duplicate"
                ],
                "is_duplicate": result["is_duplicate"],
                "recommendation": result["recommendation"],
            })

    duplicate_matches.sort(
        key=lambda item: item["similarity"],
        reverse=True
    )

    return duplicate_matches
