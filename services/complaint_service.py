
"""
Civic Connect - Complaint Management Service

Handles complaint validation, file uploads, duplicate detection,
AI analysis, rate limiting, and department assignment.
"""

import os
import random
import re

from datetime import datetime, timedelta
from flask import session
from werkzeug.utils import secure_filename

from database.db import get_db_connection

from ai import (
    classify_complaint,
    find_duplicate_complaints,
    predict_priority,
    summarize_complaint
)


# =====================================
# UPLOAD SETTINGS
# =====================================

UPLOAD_FOLDER = "uploads"

ALLOWED_IMAGE_EXTENSIONS = {
    "jpg", "jpeg", "png", "webp"
}

ALLOWED_VIDEO_EXTENSIONS = {
    "mp4", "mov", "avi", "webm"
}

MAX_FILE_SIZE = 50 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =====================================
# FILE VALIDATION
# =====================================

def _validate_file(file, allowed_extensions):
    if not file or not file.filename:
        return True

    filename = secure_filename(file.filename)

    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[-1].lower()

    if extension not in allowed_extensions:
        return False

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)

    return size <= MAX_FILE_SIZE


def validate_image(file):
    return _validate_file(file, ALLOWED_IMAGE_EXTENSIONS)


def validate_video(file):
    return _validate_file(file, ALLOWED_VIDEO_EXTENSIONS)


# =====================================
# SAVE UPLOADED FILE
# =====================================

def save_file(file, complaint_id):
    if not file or not file.filename:
        return None

    filename = secure_filename(file.filename)

    if not filename or "." not in filename:
        raise ValueError("Invalid uploaded filename.")

    extension = filename.rsplit(".", 1)[-1].lower()

    new_filename = (
        f"{complaint_id}_"
        f"{random.randint(1000, 9999)}."
        f"{extension}"
    )

    filepath = os.path.join(UPLOAD_FOLDER, new_filename)

    file.save(filepath)

    return filepath


# =====================================
# DATE VALIDATION
# =====================================

def validate_date(date_text):
    try:
        complaint_date = datetime.strptime(
            date_text,
            "%Y-%m-%d"
        ).date()

        return complaint_date <= datetime.now().date()

    except (ValueError, TypeError):
        return False


# =====================================
# LOCATION VALIDATION
# =====================================

def validate_location(location):
    if not isinstance(location, str):
        return False

    location = location.strip()

    return (
        len(location) >= 5
        and bool(re.search(r"[A-Za-z0-9]", location))
    )


# =====================================
# DESCRIPTION VALIDATION
# =====================================

def validate_description(description):
    if not isinstance(description, str):
        return False

    description = description.strip()

    return (
        len(description) >= 20
        and len(description.split()) >= 5
    )


# =====================================
# SPAM DETECTION
# =====================================

def is_spam(description):
    if not isinstance(description, str):
        return True

    description_lower = description.lower()

    spam_words = [
        "asdf",
        "qwerty",
        "test complaint",
        "hello hello",
        "abc abc",
        "fake complaint"
    ]

    for word in spam_words:
        if word in description_lower:
            return True

    if re.search(r"(.)\1{6,}", description_lower):
        return True

    return False


# =====================================
# AI COMPLAINT ANALYSIS
# =====================================

def analyze_complaint(description, location=""):
    """
    Run the AI baseline functions on a complaint.

    Returns classification, priority, and summary results.
    """

    classification = classify_complaint(
        description,
        location
    )

    priority = predict_priority(
        description,
        classification.get("category", ""),
        location
    )

    summary = summarize_complaint(description)

    return {
        "classification": classification,
        "priority": priority,
        "summary": summary
    }


# =====================================
# DUPLICATE DETECTION
# =====================================

def find_duplicate(category, location, description):
    """
    Check the latest 100 complaints for possible duplicates.

    Returns True if at least one possible duplicate is found.
    """

    connection = get_db_connection()

    try:
        complaints = connection.execute(
            """
            SELECT
                complaint_id,
                category,
                location,
                description
            FROM complaints
            ORDER BY id DESC
            LIMIT 100
            """
        ).fetchall()

        existing_complaints = [
            {
                "complaint_id": row["complaint_id"],
                "category": row["category"],
                "location": row["location"],
                "description": row["description"]
            }
            for row in complaints
        ]

    finally:
        connection.close()

    new_complaint = {
        "category": category,
        "location": location,
        "description": description
    }

    matches = find_duplicate_complaints(
        new_complaint,
        existing_complaints,
        threshold=0.75
    )

    return len(matches) > 0


# =====================================
# RATE LIMITING
# =====================================

def check_submission_rate():
    now = datetime.now()

    submissions = session.get("submissions", [])

    valid_submissions = []

    for timestamp in submissions:
        try:
            old_time = datetime.fromisoformat(timestamp)

            if now - old_time < timedelta(minutes=10):
                valid_submissions.append(timestamp)

        except (ValueError, TypeError):
            continue

    session["submissions"] = valid_submissions

    return len(valid_submissions) < 3


def record_submission():
    submissions = session.get("submissions", [])

    submissions.append(datetime.now().isoformat())

    session["submissions"] = submissions


# =====================================
# DEPARTMENT ROUTING
# =====================================

def get_department(category):
    department_mapping = {
        "Illegal Construction": "Municipality",
        "Environmental Issue": "Pollution Control",
        "Traffic Issue": "Traffic Department",
        "Public Safety": "Police"
    }

    return department_mapping.get(
        category,
        "General Civic Department"
    )
