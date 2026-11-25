
from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from database.db import (
    get_db_connection,
    create_database,
    upgrade_database,
    add_history
)
import random
import os
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from functools import wraps
from datetime import datetime


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("CIVICCONNECT_SECRET_KEY") or ""
if not app.config["SECRET_KEY"]:
    raise RuntimeError("Set CIVICCONNECT_SECRET_KEY in your environment before starting Civic Connect.")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
)


# ==============================
# FLASK SESSION
# ==============================




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


# Department choices are labels only. Credentials are stored in the users table.
DEPARTMENTS = ["Municipality", "Pollution Control", "Traffic Department", "Police"]

def authenticate_user(username, password, role, department=None):
    connection = get_db_connection()
    user = connection.execute(
        "SELECT * FROM users WHERE username = ? AND role = ? AND is_active = 1",
        (username.strip(), role)
    ).fetchone()
    connection.close()
    if user and check_password_hash(user["password_hash"], password):
        if role != "department" or user["department"] == department:
            return user
    return None

def login_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("user_role") != role:
                target = {"admin": "admin_login", "validator": "validator_login", "department": "department_login"}[role]
                return redirect(url_for(target))
            return view(*args, **kwargs)
        return wrapped
    return decorator


# ==============================
# DATABASE CONNECTION
# ==============================




# ==============================
# CREATE DATABASE
# ==============================

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

    number1 = random.randint(1, 9)

    number2 = random.randint(1, 9)

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

    file.seek(0, 2)

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

    file.seek(0, 2)

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

def validate_description(description):

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

    session["submissions"] = valid_submissions

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

        image = request.files.get("image")

        video = request.files.get("video")

        # CAPTCHA

        correct_captcha = session.get(
            "captcha_answer"
        )

        try:

            captcha_answer = int(captcha)

        except ValueError:

            captcha_answer = -1

        if (
            correct_captcha is None
            or captcha_answer != correct_captcha
        ):

            captcha_question = generate_captcha()

            return render_template(
                "report.html",
                error="Incorrect CAPTCHA. Please try again.",
                captcha_question=captcha_question,
                category=category,
                location=location,
                date=date,
                description=description
            )

        # CATEGORY

        valid_categories = [

            "Illegal Construction",

            "Environmental Issue",

            "Traffic Issue",

            "Public Safety",

            "Other Civic Issue"

        ]

        if category not in valid_categories:

            captcha_question = generate_captcha()

            return render_template(
                "report.html",
                error="Please select a valid complaint category.",
                captcha_question=captcha_question
            )

        # LOCATION

        if not validate_location(location):

            captcha_question = generate_captcha()

            return render_template(
                "report.html",
                error="Please provide a valid location.",
                captcha_question=captcha_question
            )

        # DATE

        if not validate_date(date):

            captcha_question = generate_captcha()

            return render_template(
                "report.html",
                error=(
                    "Please provide a valid date. "
                    "Future dates are not allowed."
                ),
                captcha_question=captcha_question
            )

        # DESCRIPTION

        if not validate_description(description):

            captcha_question = generate_captcha()

            return render_template(
                "report.html",
                error=(
                    "Description must contain at least "
                    "20 characters and 5 words."
                ),
                captcha_question=captcha_question
            )

        # IMAGE

        if not validate_image(image):

            captcha_question = generate_captcha()

            return render_template(
                "report.html",
                error=(
                    "Invalid image. Use JPG, JPEG, PNG "
                    "or WEBP under 50 MB."
                ),
                captcha_question=captcha_question
            )

        # VIDEO

        if not validate_video(video):

            captcha_question = generate_captcha()

            return render_template(
                "report.html",
                error=(
                    "Invalid video. Use MP4, MOV, AVI "
                    "or WEBM under 50 MB."
                ),
                captcha_question=captcha_question
            )

        # RATE LIMIT

        if not check_submission_rate():

            captcha_question = generate_captcha()

            return render_template(
                "report.html",
                error=(
                    "Too many complaints submitted. "
                    "Please try again later."
                ),
                captcha_question=captcha_question
            )

        # DUPLICATE

        duplicate = find_duplicate(
            category,
            location,
            description
        )

        # SPAM

        spam = is_spam(description)

        # SUSPICION SCORE

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

        if not image and not video:

            suspicion_score += 10

            validation_messages.append(
                "No supporting evidence provided."
            )

        # STATUS

        if suspicion_score >= 50:

            status = "Flagged for Review"

        else:

            status = "Assigned"

        # COMPLAINT ID

        connection = get_db_connection()

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

        # DEPARTMENT

        department = get_department(category)

        # SAVE FILES

        image_path = save_file(
            image,
            complaint_id
        )

        video_path = save_file(
            video,
            complaint_id
        )

        # VALIDATION MESSAGE

        if validation_messages:

            validation_message = " ".join(
                validation_messages
            )

        else:

            validation_message = (
                "Complaint passed automatic validation "
                "and was assigned to the concerned department."
            )

        # SAVE COMPLAINT

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

        # COMPLAINT HISTORY

        add_history(
            complaint_id,
            "Complaint Submitted",
            "Citizen",
            "Complaint submitted successfully."
        )

        # AUTOMATIC VALIDATION HISTORY

        if status == "Flagged for Review":

            add_history(
                complaint_id,
                "Flagged for Review",
                "Automatic Validation",
                validation_message
            )

        else:

            add_history(
                complaint_id,
                "Automatically Validated",
                "Automatic Validation",
                validation_message
            )

            # ASSIGNMENT HISTORY

            add_history(
                complaint_id,
                "Assigned",
                "System",
                "Assigned to " + department + "."
            )

        # RECORD SUBMISSION

        record_submission()

        # NEW CAPTCHA

        generate_captcha()

        # SUCCESS

        return render_template(
            "success.html",
            complaint_id=complaint_id,
            category=category,
            department=department,
            status=status,
            validation_message=validation_message
        )

    # GET REPORT PAGE

    captcha_question = generate_captcha()

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

    history = []

    error = None

    if request.method == "POST":

        complaint_id = request.form.get(
            "complaint_id",
            ""
        ).strip().upper()

        connection = get_db_connection()

        complaint = connection.execute(
            """
            SELECT *
            FROM complaints
            WHERE complaint_id = ?
            """,
            (complaint_id,)
        ).fetchone()

        if complaint is not None:

            history = connection.execute(
                """
                SELECT *
                FROM complaint_history
                WHERE complaint_id = ?
                ORDER BY id ASC
                """,
                (complaint_id,)
            ).fetchall()

        connection.close()

        if complaint is None:

            error = "Complaint ID not found."

    return render_template(
        "track.html",
        complaint=complaint,
        history=history,
        error=error
    )


# ==============================
# VALIDATOR LOGIN
# ==============================

@app.route("/validator-login", methods=["GET", "POST"])
def validator_login():
    error = None
    if request.method == "POST":
        user = authenticate_user(request.form.get("username", ""), request.form.get("password", ""), "validator")
        if user:
            session.clear()
            session.update(user_id=user["id"], username=user["username"], user_role="validator", validator_logged_in=True)
            session.permanent = True
            return redirect(url_for("validator"))
        error = "Invalid username or password, or account is inactive."
    return render_template("validator_login.html", error=error)


# ==============================
# VALIDATOR DASHBOARD
# ==============================

@app.route("/validator")
def validator():

    if session.get("user_role") != "validator":

        return redirect("/validator-login")

    connection = get_db_connection()

    complaints = connection.execute(
        """
        SELECT *
        FROM complaints
        WHERE status = ?
        ORDER BY id DESC
        """,
        ("Flagged for Review",)
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
def validate_complaint(complaint_id):

    if session.get("user_role") != "validator":

        return redirect("/validator-login")

    connection = get_db_connection()

    result = connection.execute(
        """
        UPDATE complaints
        SET status = ?
        WHERE complaint_id = ?
        AND status = ?
        """,
        (
            "Assigned",
            complaint_id,
            "Flagged for Review"
        )
    )

    connection.commit()

    connection.close()

    if result.rowcount > 0:

        add_history(
            complaint_id,
            "Assigned",
            "Validator",
            "Complaint validated and assigned to the concerned department."
        )

    return redirect("/validator")


# ==============================
# REJECT COMPLAINT
# ==============================

@app.route(
    "/reject/<complaint_id>",
    methods=["POST"]
)
def reject_complaint(complaint_id):

    if session.get("user_role") != "validator":

        return redirect("/validator-login")

    connection = get_db_connection()

    result = connection.execute(
        """
        UPDATE complaints
        SET status = ?
        WHERE complaint_id = ?
        AND status = ?
        """,
        (
            "Rejected",
            complaint_id,
            "Flagged for Review"
        )
    )

    connection.commit()

    connection.close()

    if result.rowcount > 0:

        add_history(
            complaint_id,
            "Rejected",
            "Validator",
            "Complaint rejected during validation."
        )

    return redirect("/validator")


# ==============================
# VALIDATOR LOGOUT
# ==============================

@app.route("/validator-logout")
def validator_logout():

    session.clear()

    return redirect("/validator-login")


# ==================================================
# DEPARTMENT LOGIN
# ==================================================

@app.route("/department-login", methods=["GET", "POST"])
def department_login():
    error = None
    selected_department = ""
    if request.method == "POST":
        selected_department = request.form.get("department", "").strip()
        if selected_department not in DEPARTMENTS:
            error = "Please select a valid department."
        else:
            user = authenticate_user(request.form.get("username", ""), request.form.get("password", ""), "department", selected_department)
            if user:
                session.clear()
                session.update(user_id=user["id"], username=user["username"], user_role="department", department=selected_department, department_logged_in=True)
                session.permanent = True
                return redirect(url_for("department_dashboard", department=selected_department))
            error = "Invalid credentials or inactive account for the selected department."
    return render_template("department_login.html", departments=DEPARTMENTS, error=error, selected_department=selected_department)


# ==================================================
# DEPARTMENT DASHBOARD
# ==================================================

@app.route(
    "/department/<department>"
)
def department_dashboard(department):

    # CHECK LOGIN

    if session.get("user_role") != "department":

        return redirect(
            url_for("department_login")
        )

    logged_department = session.get("department")

    # PREVENT ACCESS TO OTHER DEPARTMENTS

    if logged_department != department:

        return redirect(
            url_for(
                "department_dashboard",
                department=logged_department
            )
        )

    # FETCH DEPARTMENT COMPLAINTS

    connection = get_db_connection()

    complaints = connection.execute(
        """
        SELECT *
        FROM complaints
        WHERE department = ?
        AND status IN (?, ?)
        ORDER BY id DESC
        """,
        (
            logged_department,
            "Assigned",
            "Under Review"
        )
    ).fetchall()

    connection.close()

    return render_template(
        "department.html",
        department=logged_department,
        complaints=complaints
    )


# ==================================================
# START REVIEW
# ==================================================

@app.route(
    "/department/review/<complaint_id>",
    methods=["POST"]
)
def start_review(complaint_id):

    if session.get("user_role") != "department":

        return redirect(
            url_for("department_login")
        )

    department = session.get("department")

    connection = get_db_connection()

    result = connection.execute(
        """
        UPDATE complaints
        SET status = ?
        WHERE complaint_id = ?
        AND department = ?
        AND status = ?
        """,
        (
            "Under Review",
            complaint_id,
            department,
            "Assigned"
        )
    )

    connection.commit()

    connection.close()

    if result.rowcount > 0:

        add_history(
            complaint_id,
            "Under Review",
            department,
            "Department started reviewing the complaint."
        )

    return redirect(
        url_for(
            "department_dashboard",
            department=department
        )
    )


# ==================================================
# MARK RESOLVED
# ==================================================

@app.route(
    "/department/resolve/<complaint_id>",
    methods=["POST"]
)
def resolve_complaint(complaint_id):

    if session.get("user_role") != "department":

        return redirect(
            url_for("department_login")
        )

    department = session.get("department")

    connection = get_db_connection()

    result = connection.execute(
        """
        UPDATE complaints
        SET status = ?
        WHERE complaint_id = ?
        AND department = ?
        AND status = ?
        """,
        (
            "Resolved",
            complaint_id,
            department,
            "Under Review"
        )
    )

    connection.commit()

    connection.close()

    if result.rowcount > 0:

        add_history(
            complaint_id,
            "Resolved",
            department,
            "Complaint resolved by department."
        )

    return redirect(
        url_for(
            "department_dashboard",
            department=department
        )
    )


# ==================================================
# DEPARTMENT LOGOUT
# ==================================================

@app.route(
    "/department-logout"
)
def department_logout():

    session.clear()

    return redirect(
        url_for("department_login")
    )


# ==================================================
# ADMIN LOGIN
# ==================================================

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        user = authenticate_user(request.form.get("username", ""), request.form.get("password", ""), "admin")
        if user:
            session.clear()
            session.update(user_id=user["id"], username=user["username"], user_role="admin", admin_logged_in=True)
            session.permanent = True
            return redirect(url_for("admin_dashboard"))
        error = "Invalid username or password, or account is inactive."
    return render_template("admin_login.html", error=error)


# ==================================================
# ADMIN DASHBOARD
# ==================================================

@app.route("/admin")
def admin_dashboard():

    if session.get("user_role") != "admin":

        return redirect("/admin-login")

    connection = get_db_connection()

    total = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM complaints
        """
    ).fetchone()["count"]

    assigned = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = ?
        """,
        ("Assigned",)
    ).fetchone()["count"]

    under_review = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = ?
        """,
        ("Under Review",)
    ).fetchone()["count"]

    resolved = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = ?
        """,
        ("Resolved",)
    ).fetchone()["count"]

    flagged = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = ?
        """,
        ("Flagged for Review",)
    ).fetchone()["count"]

    rejected = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = ?
        """,
        ("Rejected",)
    ).fetchone()["count"]

    department_summary = connection.execute(
        """
        SELECT
            department,
            COUNT(*) AS count
        FROM complaints
        GROUP BY department
        ORDER BY count DESC
        """
    ).fetchall()

    recent_complaints = connection.execute(
        """
        SELECT
            complaint_id,
            category,
            department,
            status,
            date
        FROM complaints
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

    staff_users = connection.execute("SELECT id, username, role, department, is_active, created_at FROM users WHERE role IN ('validator','department') ORDER BY role, username").fetchall()
    connection.close()

    return render_template(
        "admin.html",
        total=total,
        assigned=assigned,
        under_review=under_review,
        resolved=resolved,
        flagged=flagged,
        rejected=rejected,
        department_summary=department_summary,
        recent_complaints=recent_complaints,
        staff_users=staff_users,
        account_error=request.args.get("account_error"),
        account_created=request.args.get("account_created")
    )


@app.route("/admin/users", methods=["POST"])
@login_required("admin")
def create_staff_user():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "")
    department = request.form.get("department", "").strip() or None
    error = None
    if len(username) < 4 or len(username) > 40:
        error = "Username must contain 4 to 40 characters."
    elif len(password) < 12:
        error = "Use a password with at least 12 characters."
    elif role not in ("validator", "department"):
        error = "Only Validator and Department accounts can be created here."
    elif role == "department" and department not in DEPARTMENTS:
        error = "Select a valid department."
    elif role == "validator":
        department = None
    if error:
        return redirect(url_for("admin_dashboard", account_error=error))
    connection = get_db_connection()
    try:
        from werkzeug.security import generate_password_hash
        connection.execute("INSERT INTO users (username,password_hash,role,department,created_at) VALUES (?,?,?,?,?)",
            (username, generate_password_hash(password), role, department, datetime.now().isoformat()))
        connection.commit()
    except sqlite3.IntegrityError:
        return redirect(url_for("admin_dashboard", account_error="That username already exists."))
    finally:
        connection.close()
    return redirect(url_for("admin_dashboard", account_created="1"))

@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@login_required("admin")
def toggle_staff_user(user_id):
    connection = get_db_connection()
    connection.execute("UPDATE users SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=? AND role IN ('validator','department')", (user_id,))
    connection.commit(); connection.close()
    return redirect(url_for("admin_dashboard"))

# ==================================================
# ADMIN LOGOUT
# ==================================================

@app.route(
    "/admin-logout"
)
def admin_logout():

    session.clear()

    return redirect("/admin-login")


# ==============================
# START APPLICATION
# ==============================

create_database()
upgrade_database()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
