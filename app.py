from flask import Flask, render_template, request, redirect, session
import sqlite3
import random
import os
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from werkzeug.utils import secure_filename


app = Flask(__name__)


# ==============================
# FLASK SESSION
# ==============================

app.secret_key = "civicconnect_secret_key"


# ==============================
# UPLOAD SETTINGS
# ==============================

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


# ==============================
# DATABASE CONNECTION
# ==============================

def get_db_connection():

    connection = sqlite3.connect(
        "civicconnect.db"
    )

    connection.row_factory = sqlite3.Row

    return connection


# ==============================
# CREATE DATABASE
# ==============================

def create_database():

    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS complaints (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            complaint_id TEXT UNIQUE NOT NULL,

            category TEXT NOT NULL,

            location TEXT NOT NULL,

            date TEXT NOT NULL,

            description TEXT NOT NULL,

            status TEXT NOT NULL,

            department TEXT NOT NULL,

            image_path TEXT,

            video_path TEXT,

            suspicion_score INTEGER DEFAULT 0,

            validation_message TEXT,

            created_at TEXT NOT NULL

        )
    """)

    connection.commit()

    connection.close()


# ==============================
# UPGRADE OLD DATABASE
# ==============================

def upgrade_database():

    connection = get_db_connection()

    columns = connection.execute(
        "PRAGMA table_info(complaints)"
    ).fetchall()

    existing_columns = [
        column["name"]
        for column in columns
    ]

    required_columns = {

        "image_path": "TEXT",

        "video_path": "TEXT",

        "suspicion_score": "INTEGER DEFAULT 0",

        "validation_message": "TEXT",

        "created_at": "TEXT"

    }

    for column, datatype in required_columns.items():

        if column not in existing_columns:

            connection.execute(
                f"""
                ALTER TABLE complaints
                ADD COLUMN {column} {datatype}
                """
            )

    connection.commit()

    connection.close()


# ==============================
# HOME PAGE
# ==============================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ==============================
# CAPTCHA
# ==============================

def generate_captcha():

    number1 = random.randint(
        1,
        9
    )

    number2 = random.randint(
        1,
        9
    )

    answer = number1 + number2

    session["captcha_answer"] = answer

    return f"{number1} + {number2} = ?"


# ==============================
# IMAGE VALIDATION
# ==============================

def validate_image(file):

    if not file or file.filename == "":
        return True

    filename = secure_filename(
        file.filename
    )

    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:

        return False

    file.seek(
        0,
        2
    )

    size = file.tell()

    file.seek(0)

    if size > MAX_FILE_SIZE:

        return False

    return True


# ==============================
# VIDEO VALIDATION
# ==============================

def validate_video(file):

    if not file or file.filename == "":
        return True

    filename = secure_filename(
        file.filename
    )

    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()

    if extension not in ALLOWED_VIDEO_EXTENSIONS:

        return False

    file.seek(
        0,
        2
    )

    size = file.tell()

    file.seek(0)

    if size > MAX_FILE_SIZE:

        return False

    return True


# ==============================
# SAVE UPLOADED FILE
# ==============================

def save_file(
    file,
    complaint_id
):

    if not file or file.filename == "":
        return None

    filename = secure_filename(
        file.filename
    )

    extension = filename.rsplit(
        ".",
        1
    )[-1].lower()

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


# ==============================
# DATE VALIDATION
# ==============================

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


# ==============================
# LOCATION VALIDATION
# ==============================

def validate_location(location):

    location = location.strip()

    if len(location) < 5:

        return False

    if not re.search(
        r"[A-Za-z0-9]",
        location
    ):

        return False

    return True


# ==============================
# DESCRIPTION VALIDATION
# ==============================

def validate_description(
    description
):

    description = description.strip()

    if len(description) < 20:

        return False

    words = description.split()

    if len(words) < 5:

        return False

    return True


# ==============================
# SPAM DETECTION
# ==============================

def is_spam(description):

    description_lower = (
        description.lower()
    )

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

    # Detect repeated characters

    if re.search(
        r"(.)\1{6,}",
        description_lower
    ):

        return True

    return False


# ==============================
# DUPLICATE DETECTION
# ==============================

def find_duplicate(
    category,
    location,
    description
):

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


# ==============================
# RATE LIMITING
# ==============================

def check_submission_rate():

    now = datetime.now()

    submissions = session.get(
        "submissions",
        []
    )

    valid_submissions = []

    for timestamp in submissions:

        try:

            old_time = datetime.fromisoformat(
                timestamp
            )

            if (
                now - old_time
                < timedelta(minutes=10)
            ):

                valid_submissions.append(
                    timestamp
                )

        except ValueError:

            pass

    session["submissions"] = (
        valid_submissions
    )

    if len(valid_submissions) >= 3:

        return False

    return True


# ==============================
# RECORD SUBMISSION
# ==============================

def record_submission():

    submissions = session.get(
        "submissions",
        []
    )

    submissions.append(
        datetime.now().isoformat()
    )

    session["submissions"] = submissions


# ==============================
# DEPARTMENT ROUTING
# ==============================

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


# ==============================
# REPORT COMPLAINT
# ==============================

@app.route(
    "/report",
    methods=["GET", "POST"]
)
def report():

    if request.method == "POST":

        # --------------------------
        # GET FORM DATA
        # --------------------------

        category = request.form.get(
            "category",
            ""
        ).strip()

        location = request.form.get(
            "location",
            ""
        ).strip()

        date = request.form.get(
            "date",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        captcha = request.form.get(
            "captcha",
            ""
        ).strip()

        image = request.files.get(
            "image"
        )

        video = request.files.get(
            "video"
        )


        # --------------------------
        # CAPTCHA
        # --------------------------

        correct_captcha = session.get(
            "captcha_answer"
        )

        try:

            captcha_answer = int(
                captcha
            )

        except ValueError:

            captcha_answer = -1

        if (
            correct_captcha is None
            or captcha_answer != correct_captcha
        ):

            captcha_question = (
                generate_captcha()
            )

            return render_template(
                "report.html",
                error=(
                    "Incorrect CAPTCHA. "
                    "Please try again."
                ),
                captcha_question=(
                    captcha_question
                )
            )


        # --------------------------
        # CATEGORY
        # --------------------------

        valid_categories = [

            "Illegal Construction",

            "Environmental Issue",

            "Traffic Issue",

            "Public Safety"

        ]

        if category not in valid_categories:

            captcha_question = (
                generate_captcha()
            )

            return render_template(
                "report.html",
                error=(
                    "Please select a valid "
                    "complaint category."
                ),
                captcha_question=(
                    captcha_question
                )
            )


        # --------------------------
        # LOCATION
        # --------------------------

        if not validate_location(
            location
        ):

            captcha_question = (
                generate_captcha()
            )

            return render_template(
                "report.html",
                error=(
                    "Please provide a "
                    "valid location."
                ),
                captcha_question=(
                    captcha_question
                )
            )


        # --------------------------
        # DATE
        # --------------------------

        if not validate_date(
            date
        ):

            captcha_question = (
                generate_captcha()
            )

            return render_template(
                "report.html",
                error=(
                    "Please provide a valid "
                    "date. Future dates are "
                    "not allowed."
                ),
                captcha_question=(
                    captcha_question
                )
            )


        # --------------------------
        # DESCRIPTION
        # --------------------------

        if not validate_description(
            description
        ):

            captcha_question = (
                generate_captcha()
            )

            return render_template(
                "report.html",
                error=(
                    "Description must contain "
                    "at least 20 characters "
                    "and 5 words."
                ),
                captcha_question=(
                    captcha_question
                )
            )


        # --------------------------
        # IMAGE
        # --------------------------

        if not validate_image(
            image
        ):

            captcha_question = (
                generate_captcha()
            )

            return render_template(
                "report.html",
                error=(
                    "Invalid image. Use JPG, "
                    "JPEG, PNG or WEBP under "
                    "50 MB."
                ),
                captcha_question=(
                    captcha_question
                )
            )


        # --------------------------
        # VIDEO
        # --------------------------

        if not validate_video(
            video
        ):

            captcha_question = (
                generate_captcha()
            )

            return render_template(
                "report.html",
                error=(
                    "Invalid video. Use MP4, "
                    "MOV, AVI or WEBM under "
                    "50 MB."
                ),
                captcha_question=(
                    captcha_question
                )
            )


        # --------------------------
        # RATE LIMIT
        # --------------------------

        if not check_submission_rate():

            captcha_question = (
                generate_captcha()
            )

            return render_template(
                "report.html",
                error=(
                    "Too many complaints "
                    "submitted. Please try "
                    "again later."
                ),
                captcha_question=(
                    captcha_question
                )
            )


        # --------------------------
        # DUPLICATE
        # --------------------------

        duplicate = find_duplicate(
            category,
            location,
            description
        )


        # --------------------------
        # SPAM
        # --------------------------

        spam = is_spam(
            description
        )


        # --------------------------
        # SUSPICION SCORE
        # --------------------------

        suspicion_score = 0

        validation_messages = []


        if duplicate:

            suspicion_score += 50

            validation_messages.append(
                "Possible duplicate complaint."
            )


        if spam:

            suspicion_score += 40

            validation_messages.append(
                "Possible spam content."
            )


        # Lack of evidence is NOT
        # treated as a false complaint.

        if (
            not image
            and not video
        ):

            suspicion_score += 10

            validation_messages.append(
                "No supporting evidence provided."
            )


        # --------------------------
        # STATUS
        # --------------------------

        if suspicion_score >= 50:

            status = "Flagged for Review"

        else:

            status = "Assigned"


        # --------------------------
        # COMPLAINT ID
        # --------------------------

        connection = (
            get_db_connection()
        )

        while True:

            complaint_id = (
                "CMP"
                + str(
                    random.randint(
                        10000,
                        99999
                    )
                )
            )

            existing = connection.execute(
                """
                SELECT complaint_id
                FROM complaints
                WHERE complaint_id = ?
                """,
                (complaint_id,)
            ).fetchone()

            if not existing:

                break


        # --------------------------
        # DEPARTMENT
        # --------------------------

        department = get_department(
            category
        )


        # --------------------------
        # SAVE FILES
        # --------------------------

        image_path = save_file(
            image,
            complaint_id
        )

        video_path = save_file(
            video,
            complaint_id
        )


        # --------------------------
        # VALIDATION MESSAGE
        # --------------------------

        if validation_messages:

            validation_message = " ".join(
                validation_messages
            )

        else:

            validation_message = (
                "Complaint passed automatic "
                "validation and was assigned "
                "to the concerned department."
            )


        # --------------------------
        # SAVE COMPLAINT
        # --------------------------

        connection.execute(
            """
            INSERT INTO complaints
            (
                complaint_id,
                category,
                location,
                date,
                description,
                status,
                department,
                image_path,
                video_path,
                suspicion_score,
                validation_message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                complaint_id,
                category,
                location,
                date,
                description,
                status,
                department,
                image_path,
                video_path,
                suspicion_score,
                validation_message,
                datetime.now().isoformat()
            )
        )

        connection.commit()

        connection.close()


        # --------------------------
        # RECORD SUBMISSION
        # --------------------------

        record_submission()


        # --------------------------
        # NEW CAPTCHA
        # --------------------------

        generate_captcha()


        # --------------------------
        # SUCCESS
        # --------------------------

        return render_template(
            "success.html",
            complaint_id=complaint_id,
            category=category,
            department=department,
            status=status,
            validation_message=validation_message
        )


    # ==============================
    # GET REPORT PAGE
    # ==============================

    captcha_question = (
        generate_captcha()
    )

    return render_template(
        "report.html",
        captcha_question=captcha_question
    )


# ==============================
# TRACK COMPLAINT
# ==============================

@app.route(
    "/track",
    methods=["GET", "POST"]
)
def track():

    complaint = None

    error = None

    if request.method == "POST":

        complaint_id = request.form[
            "complaint_id"
        ].strip().upper()

        connection = (
            get_db_connection()
        )

        complaint = connection.execute(
            """
            SELECT *
            FROM complaints
            WHERE complaint_id = ?
            """,
            (complaint_id,)
        ).fetchone()

        connection.close()

        if complaint is None:

            error = (
                "Complaint ID not found."
            )


    return render_template(
        "track.html",
        complaint=complaint,
        error=error
    )


# ==============================
# VALIDATOR LOGIN
# ==============================

@app.route(
    "/validator-login",
    methods=["GET", "POST"]
)
def validator_login():

    error = None

    if request.method == "POST":

        username = request.form[
            "username"
        ]

        password = request.form[
            "password"
        ]

        if (
            username == "validator"
            and password == "civic123"
        ):

            session[
                "validator_logged_in"
            ] = True

            return redirect(
                "/validator"
            )

        else:

            error = (
                "Invalid username or password."
            )


    return render_template(
        "validator_login.html",
        error=error
    )


# ==============================
# VALIDATOR DASHBOARD
# ==============================

@app.route("/validator")
def validator():

    if not session.get(
        "validator_logged_in"
    ):

        return redirect(
            "/validator-login"
        )


    connection = (
        get_db_connection()
    )

    complaints = connection.execute(
        """
        SELECT *
        FROM complaints
        WHERE status = ?
        ORDER BY id DESC
        """,
        (
            "Flagged for Review",
        )
    ).fetchall()

    connection.close()

    return render_template(
        "validator.html",
        complaints=complaints
    )


# ==============================
# VALIDATE FLAGGED COMPLAINT
# ==============================

@app.route(
    "/validate/<complaint_id>",
    methods=["POST"]
)
def validate_complaint(
    complaint_id
):

    if not session.get(
        "validator_logged_in"
    ):

        return redirect(
            "/validator-login"
        )


    connection = (
        get_db_connection()
    )

    connection.execute(
        """
        UPDATE complaints
        SET status = ?
        WHERE complaint_id = ?
        """,
        (
            "Assigned",
            complaint_id
        )
    )

    connection.commit()

    connection.close()

    return redirect(
        "/validator"
    )


# ==============================
# REJECT COMPLAINT
# ==============================

@app.route(
    "/reject/<complaint_id>",
    methods=["POST"]
)
def reject_complaint(
    complaint_id
):

    if not session.get(
        "validator_logged_in"
    ):

        return redirect(
            "/validator-login"
        )


    connection = (
        get_db_connection()
    )

    connection.execute(
        """
        UPDATE complaints
        SET status = ?
        WHERE complaint_id = ?
        """,
        (
            "Rejected",
            complaint_id
        )
    )

    connection.commit()

    connection.close()

    return redirect(
        "/validator"
    )


# ==============================
# VALIDATOR LOGOUT
# ==============================

@app.route(
    "/validator-logout"
)
def validator_logout():

    session.pop(
        "validator_logged_in",
        None
    )

    return redirect(
        "/validator-login"
    )


# ==============================
# DEPARTMENT DASHBOARD
# ==============================

@app.route(
    "/department/<department>"
)
def department_dashboard(
    department
):

    # Temporary department access.
    # Authentication can be added later.

    connection = (
        get_db_connection()
    )

    complaints = connection.execute(
        """
        SELECT *
        FROM complaints
        WHERE department = ?
        AND status IN (?, ?)
        ORDER BY id DESC
        """,
        (
            department,
            "Assigned",
            "Under Review"
        )
    ).fetchall()

    connection.close()

    return render_template(
        "department.html",
        department=department,
        complaints=complaints
    )


# ==============================
# START REVIEW
# ==============================

@app.route(
    "/department/review/<complaint_id>",
    methods=["POST"]
)
def start_review(
    complaint_id
):

    connection = (
        get_db_connection()
    )

    connection.execute(
        """
        UPDATE complaints
        SET status = ?
        WHERE complaint_id = ?
        AND status = ?
        """,
        (
            "Under Review",
            complaint_id,
            "Assigned"
        )
    )

    connection.commit()

    connection.close()

    return redirect(
        request.referrer
        or "/"
    )


# ==============================
# MARK RESOLVED
# ==============================

@app.route(
    "/department/resolve/<complaint_id>",
    methods=["POST"]
)
def resolve_complaint(
    complaint_id
):

    connection = (
        get_db_connection()
    )

    connection.execute(
        """
        UPDATE complaints
        SET status = ?
        WHERE complaint_id = ?
        AND status = ?
        """,
        (
            "Resolved",
            complaint_id,
            "Under Review"
        )
    )

    connection.commit()

    connection.close()

    return redirect(
        request.referrer
        or "/"
    )


# ==============================
# START APPLICATION
# ==============================

if __name__ == "__main__":

    create_database()

    upgrade_database()

    app.run(
        debug=True
    )