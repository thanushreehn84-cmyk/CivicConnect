
import os
from pathlib import Path

# Project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Database configuration
DATABASE_NAME = os.environ.get(
    "CIVICCONNECT_DATABASE",
    str(BASE_DIR / "civicconnect.db")
)

# Flask security
SECRET_KEY = os.environ.get(
    "CIVICCONNECT_SECRET_KEY",
    "development-only-change-this-secret-key"
)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.environ.get(
    "FLASK_HTTPS",
    "false"
).lower() == "true"

PERMANENT_SESSION_LIFETIME = 1800

# Upload configuration
UPLOAD_FOLDER = str(BASE_DIR / "uploads")

ALLOWED_IMAGE_EXTENSIONS = {
    "jpg", "jpeg", "png", "webp"
}

ALLOWED_VIDEO_EXTENSIONS = {
    "mp4", "mov", "avi", "webm"
}

MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_CONTENT_LENGTH = MAX_FILE_SIZE

# Create upload directory if it does not exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Department names
DEPARTMENTS = (
    "Municipality",
    "Pollution Control",
    "Traffic Department",
    "Police"
)
