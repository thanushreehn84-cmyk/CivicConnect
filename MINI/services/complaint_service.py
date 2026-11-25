
import os
import random
import re

from datetime import datetime, timedelta
from difflib import SequenceMatcher

from flask import session
from werkzeug.utils import secure_filename

from database.db import get_db_connection, add_history


# =====================================
# UPLOAD SETTINGS
# =====================================

UPLOAD_FOLDER = "uploads"

ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}

ALLOWED_VIDEO_EXTENSIONS = {
    "mp4",
    "mov",
    "avi",
    "webm"
}

MAX_FILE_SIZE = 50 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =====================================
# IMAGE VALIDATION
# =====================================

def validate_image(file):

    if not file or file.filename == "":
        return True

    filename = secure_filename(file.filename)

    extension = filename.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return False

    file.seek(0, 2)

    size = file.tell()

    file.seek(0)

    if size > MAX_FILE_SIZE:
        return False

    return True


# =====================================
# VIDEO VALIDATION
# =====================================

def validate_video(file):

    if not file or file.filename == "":
        return True

    filename = secure_filename(file.filename)

    extension = filename.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        return False

    file.seek(0, 2)

    size = file.tell()

    file.seek(0)

    if size > MAX_FILE_SIZE:
        return False

    return True


# =====================================
# SAVE UPLOADED FILE
# =====================================

def save_file(file, complaint_id):

    if not file or file.filename == "":
        return None

    filename = secure_filename(file.filename)

    extension = filename.rsplit(".", 1)[-1].lower()

    new_filename = (
        f"{complaint_id}_"
        f"{random.randint(1000, 9999)}."
        f"{extension}"
    )

    filepath = os.path.join(
        UPLOAD_FOLDER,
        new_filename
    )

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

        today = datetime.now().date()

        if complaint_date > today:
            return False

        return True

    except ValueError:

        return False


# =====================================
# LOCATION VALIDATION
# =====================================

def validate_location(location):

    location = location.strip()

    if len(location) < 5:
        return False

    if not re.search(r"[A-Za-z0-9]", location):
        return False

    return True


# =====================================
# DESCRIPTION VALIDATION
# =====================================

def validate_description(description):

    description = description.strip()

    if len(description) < 20:
        return False

    words = description.split()

    if len(words) < 5:
        return False

    return True


# =====================================
# SPAM DETECTION
# =====================================

def is_spam(description):

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
# DUPLICATE DETECTION
# =====================================

def find_duplicate(category, location, description):

    connection = get_db_connection()

    complaints = connection.execute(
        """
        SELECT
            category,
            location,
            description
        FROM complaints
        ORDER BY id DESC
        LIMIT 100
        """
    ).fetchall()

    connection.close()

    new_text = (
        category.lower()
        + " "
        + location.lower()
        + " "
        + description.lower()
    )

    for complaint in complaints:

        old_text = (
            complaint["category"].lower()
            + " "
            + complaint["location"].lower()
            + " "
            + complaint["description"].lower()
        )

        similarity = SequenceMatcher(
            None,
            new_text,
            old_text
        ).ratio()

        if similarity >= 0.85:
            return True

    return False


# =====================================
# RATE LIMITING
# =====================================

def check_submission_rate():

    now = datetime.now()

    submissions = session.get(
        "submissions",
        []
    )

    valid_submissions = []

    for timestamp in submissions:

        try:

            old_time = datetime.fromisoformat(timestamp)

            if now - old_time < timedelta(minutes=10):

                valid_submissions.append(timestamp)

        except ValueError:

            pass

    session["submissions"] = valid_submissions

    if len(valid_submissions) >= 3:
        return False

    return True


# =====================================
# RECORD SUBMISSION
# =====================================

def record_submission():

    submissions = session.get(
        "submissions",
        []
    )

    submissions.append(
        datetime.now().isoformat()
    )

    session["submissions"] = submissions


# =====================================
# DEPARTMENT ROUTING
# =====================================

def get_department(category):

    if category == "Illegal Construction":
        return "Municipality"

    elif category == "Environmental Issue":
        return "Pollution Control"

    elif category == "Traffic Issue":
        return "Traffic Department"

    elif category == "Public Safety":
        return "Police"

    return "General Civic Department"
