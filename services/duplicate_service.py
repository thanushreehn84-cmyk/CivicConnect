"""
Civic Connect - Duplicate Detection Service

Checks new complaints against existing database records
using the AI similarity-based duplicate detector.
"""

from database.db import get_db_connection
from ai import find_duplicate_complaints


def find_possible_duplicates(
    description,
    location,
    category,
    threshold=0.75,
    limit=100,
    exclude_statuses=("Rejected", "Resolved")
):
    """
    Find existing complaints similar to a new complaint.

    Rejected and Resolved complaints are ignored by default: a rejected
    complaint was invalid, and a resolved issue can legitimately recur.

    Returns matching complaint records with similarity scores.
    """

    if not isinstance(description, str):
        raise ValueError("Description must be text.")

    if not isinstance(location, str):
        raise ValueError("Location must be text.")

    if not isinstance(category, str):
        raise ValueError("Category must be text.")

    if not 0 <= threshold <= 1:
        raise ValueError("Threshold must be between 0 and 1.")

    if not isinstance(limit, int) or limit < 1:
        raise ValueError("Limit must be a positive integer.")

    new_complaint = {
        "description": description,
        "location": location,
        "category": category
    }

    exclude_statuses = tuple(exclude_statuses or ())
    status_filter = ""

    if exclude_statuses:
        marks = ",".join("?" for _ in exclude_statuses)
        status_filter = f"WHERE status NOT IN ({marks})"

    connection = get_db_connection()

    try:
        rows = connection.execute(
            f"""
            SELECT
                complaint_id,
                category,
                location,
                description,
                status,
                created_at
            FROM complaints
            {status_filter}
            ORDER BY id DESC
            LIMIT ?
            """,
            exclude_statuses + (limit,)
        ).fetchall()

        existing_complaints = [
            dict(row) for row in rows
        ]

    finally:
        connection.close()

    return find_duplicate_complaints(
        new_complaint,
        existing_complaints,
        threshold=threshold
    )


def is_duplicate_complaint(
    description,
    location,
    category,
    threshold=0.75
):
    """Return True when a possible duplicate is detected."""

    matches = find_possible_duplicates(
        description=description,
        location=location,
        category=category,
        threshold=threshold
    )

    return bool(matches)


def get_duplicate_summary(
    description,
    location,
    category,
    threshold=0.75
):
    """Return a simple duplicate-check result for application use."""

    matches = find_possible_duplicates(
        description=description,
        location=location,
        category=category,
        threshold=threshold
    )

    return {
        "is_duplicate": bool(matches),
        "match_count": len(matches),
        "matches": matches,
        "threshold": threshold
    }