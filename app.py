from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    url_for,
    flash,
    abort,
    send_from_directory
)

import os
import random

from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

from database.db import (
    get_db_connection,
    create_database,
    upgrade_database,
    add_history
)

from services.auth_service import (
    authenticate_user,
    VALID_DEPARTMENTS
)

from services.validation_service import (
    analyze_complaint,
    validate_date,
    validate_location,
    validate_description,
    get_review_queue,
    get_recently_reviewed,
    get_review_stats,
    update_validation_decision,
    MIN_REJECTION_REASON_LENGTH,
    MAX_REJECTION_REASON_LENGTH
)

from routes.admin import admin_bp
from routes.citizen import citizen_bp
from routes.department import department_bp
from routes.validator import validator_bp

# ==================================================
# FLASK APPLICATION
# ==================================================

app = Flask(__name__)

app.secret_key = (
    os.environ.get("CIVICCONNECT_SECRET_KEY")
    or os.urandom(32)
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(
        os.environ.get("FLASK_ENV") == "production"
    ),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8)
)

# ==================================================
# UPLOAD SETTINGS
# ==================================================

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

# ==================================================
# REGISTER BLUEPRINTS
# ==================================================

app.register_blueprint(admin_bp)
app.register_blueprint(citizen_bp)
app.register_blueprint(department_bp)
app.register_blueprint(validator_bp)

# ==================================================
# HOME PAGE
# ==================================================

@app.route("/")
def home():

    return render_template("index.html")

# ==================================================
# ROLE CHECK HELPERS
# ==================================================

def validator_required():
    return (
        session.get("validator_logged_in")
        and session.get("role") == "validator"
    )

def staff_logged_in():
    """True for any logged-in validator, department user or admin."""

    return bool(
        (
            session.get("validator_logged_in")
            and session.get("role") == "validator"
        )
        or (
            session.get("department_logged_in")
            and session.get("role") == "department"
        )
        or (
            session.get("admin_logged_in")
            and session.get("role") == "admin"
        )
    )

# ==================================================
# CAPTCHA
# ==================================================

def generate_captcha():

    number1 = random.randint(1, 9)
    number2 = random.randint(1, 9)

    answer = number1 + number2

    session["captcha_answer"] = answer

    return f"{number1} + {number2} = ?"

# ==================================================
# IMAGE VALIDATION
# ==================================================

def validate_image(file):

    if not file or not file.filename:
        return True

    filename = secure_filename(file.filename)

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        return False

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)

    if size > MAX_FILE_SIZE:
        return False

    return True

# ==================================================
# VIDEO VALIDATION
# ==================================================

def validate_video(file):

    if not file or not file.filename:
        return True

    filename = secure_filename(file.filename)

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[-1].lower()

    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        return False

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)

    if size > MAX_FILE_SIZE:
        return False

    return True

# ==================================================
# SAVE UPLOADED FILE
# ==================================================

def save_file(file, complaint_id):

    if not file or not file.filename:
        return None

    filename = secure_filename(file.filename)

    if "." not in filename:
        return None

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

# ==================================================
# RATE LIMITING
# ==================================================

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

        except (ValueError, TypeError):

            continue

    session["submissions"] = valid_submissions

    if len(valid_submissions) >= 3:
        return False

    return True

# ==================================================
# RECORD SUBMISSION
# ==================================================

def record_submission():

    submissions = session.get(
        "submissions",
        []
    )

    submissions.append(
        datetime.now().isoformat()
    )

    session["submissions"] = submissions

# ==================================================
# DEPARTMENT ROUTING
# ==================================================

def get_department(category):

    department_mapping = {

        "Illegal Construction": "Municipality",

        "Environmental Issue": "Pollution Control",

        "Traffic Issue": "Traffic Department",

        "Public Safety": "Police",

        "Other Civic Issue": "General Civic Department"

    }

    return department_mapping.get(
        category,
        "General Civic Department"
    )

# ==================================================
# SERVE UPLOADED EVIDENCE (STAFF ONLY)
# ==================================================

@app.route("/uploads/<path:filename>")
def serve_upload(filename):

    if not staff_logged_in():
        abort(403)

    return send_from_directory(
        os.path.abspath(UPLOAD_FOLDER),
        filename
    )

# ==================================================
# REPORT COMPLAINT
# ==================================================

@app.route(
    "/report",
    methods=["GET", "POST"]
)
def report():
    if request.method == "GET":
        captcha_question = generate_captcha()
        return render_template(
            "report.html",
            captcha_question=captcha_question
        )

    # Collect and normalize submitted fields.
    category = request.form.get("category", "").strip()
    location = request.form.get("location", "").strip()
    complaint_date = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()
    captcha = request.form.get("captcha", "").strip()

    image = request.files.get("image")
    video = request.files.get("video")

    def report_error(message):
        return render_template(
            "report.html",
            error=message,
            captcha_question=generate_captcha(),
            category=category,
            location=location,
            date=complaint_date,
            description=description
        )

    # CAPTCHA validation.
    correct_captcha = session.pop("captcha_answer", None)
    try:
        captcha_answer = int(captcha)
    except (ValueError, TypeError):
        captcha_answer = -1

    if correct_captcha is None or captcha_answer != correct_captcha:
        return report_error("Incorrect CAPTCHA. Please try again.")

    # Validate all user-provided fields before processing uploads.
    valid_categories = {
        "Illegal Construction",
        "Environmental Issue",
        "Traffic Issue",
        "Public Safety",
        "Other Civic Issue"
    }

    if category not in valid_categories:
        return report_error("Please select a valid complaint category.")

    if not validate_location(location):
        return report_error("Please provide a valid location.")

    if not validate_date(complaint_date):
        return report_error(
            "Please provide a valid date. Future dates are not allowed."
        )

    if not validate_description(description):
        return report_error(
            "Description must contain at least 20 characters and 5 words."
        )

    if not validate_image(image):
        return report_error(
            "Invalid image. Use JPG, JPEG, PNG or WEBP under 50 MB."
        )

    if not validate_video(video):
        return report_error(
            "Invalid video. Use MP4, MOV, AVI or WEBM under 50 MB."
        )

    if not check_submission_rate():
        return report_error(
            "Too many complaints submitted. Please try again later."
        )

    # Automatic rule-based validation: duplicate, spam, category, evidence.
    has_evidence = bool(
        (image and image.filename) or (video and video.filename)
    )

    analysis = analyze_complaint(
        category=category,
        location=location,
        description=description,
        has_evidence=has_evidence
    )

    suspicion_score = analysis["suspicion_score"]
    status = analysis["status"]
    validation_message = analysis["validation_message"]

    # Assign the responsible department. Complaints flagged for review
    # remain in the validator queue until a validator approves them.
    department = get_department(category)

    connection = get_db_connection()
    image_path = None
    video_path = None

    try:
        # Generate an ID that is not already present in the database.
        while True:
            complaint_id = f"CMP{random.randint(10000, 99999)}"
            existing = connection.execute(
                "SELECT complaint_id FROM complaints WHERE complaint_id = ?",
                (complaint_id,)
            ).fetchone()
            if not existing:
                break

        # Save evidence only after all validations have passed.
        image_path = save_file(image, complaint_id)
        video_path = save_file(video, complaint_id)

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
                validation_reasons,
                duplicate_of,
                duplicate_similarity,
                suggested_category,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                complaint_id,
                category,
                location,
                complaint_date,
                description,
                status,
                department,
                image_path,
                video_path,
                suspicion_score,
                validation_message,
                analysis["validation_reasons"],
                analysis["duplicate_of"],
                analysis["duplicate_similarity"],
                analysis["suggested_category"],
                datetime.now().isoformat()
            )
        )
        connection.commit()

    except Exception:
        connection.rollback()

        # Remove files if the database save fails.
        for filepath in (image_path, video_path):
            if filepath and os.path.exists(filepath):
                os.remove(filepath)

        raise

    finally:
        connection.close()

    # Record an auditable history of submission and automatic validation.
    add_history(
        complaint_id,
        "Complaint Submitted",
        "Citizen",
        "Complaint submitted successfully."
    )

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
        add_history(
            complaint_id,
            "Assigned",
            "System",
            "Assigned to " + department + "."
        )

    record_submission()
    generate_captcha()

    return render_template(
        "success.html",
        complaint_id=complaint_id,
        category=category,
        department=department,
        status=status,
        validation_message=validation_message
    )

# ==================================================
# TRACK COMPLAINT
# ==================================================

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

# ==================================================
# VALIDATOR LOGIN
# ==================================================

@app.route(
    "/validator-login",
    methods=["GET", "POST"]
)
def validator_login():

    error = None

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = authenticate_user(
            username,
            password,
            expected_role="validator"
        )

        if user:

            session.clear()
            session.permanent = True

            session["validator_logged_in"] = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            return redirect(url_for("validator"))

        error = (
            "Invalid username or password, "
            "or your account is inactive."
        )

    return render_template(
        "validator_login.html",
        error=error
    )

# ==================================================
# VALIDATOR DASHBOARD
# ==================================================

@app.route("/validator")
def validator():

    if not validator_required():

        return redirect("/validator-login")

    return render_template(
        "validator.html",
        complaints=get_review_queue(),
        recent_reviews=get_recently_reviewed(limit=10),
        stats=get_review_stats(),
        username=session.get("username"),
        min_reason_length=MIN_REJECTION_REASON_LENGTH,
        max_reason_length=MAX_REJECTION_REASON_LENGTH
    )

# ==================================================
# VALIDATE (APPROVE) FLAGGED COMPLAINT
# ==================================================

@app.route(
    "/validate/<complaint_id>",
    methods=["POST"]
)
def validate_complaint(complaint_id):

    if not validator_required():

        return redirect("/validator-login")

    try:

        updated = update_validation_decision(
            complaint_id,
            "approve",
            validator=session.get("username", "Validator")
        )

    except ValueError as error:

        flash(str(error), "error")
        return redirect("/validator")

    if updated:

        flash(
            f"Complaint {complaint_id} approved and assigned "
            "to its department.",
            "success"
        )

    else:

        flash(
            f"Complaint {complaint_id} could not be approved. "
            "It may already have been reviewed.",
            "error"
        )

    return redirect("/validator")

# ==================================================
# REJECT COMPLAINT
# ==================================================

@app.route(
    "/reject/<complaint_id>",
    methods=["POST"]
)
def reject_complaint(complaint_id):

    if not validator_required():

        return redirect("/validator-login")

    try:

        updated = update_validation_decision(
            complaint_id,
            "reject",
            validator=session.get("username", "Validator"),
            remarks=request.form.get("reason", "")
        )

    except ValueError as error:

        flash(str(error), "error")
        return redirect("/validator")

    if updated:

        flash(f"Complaint {complaint_id} rejected.", "success")

    else:

        flash(
            f"Complaint {complaint_id} could not be rejected. "
            "It may already have been reviewed.",
            "error"
        )

    return redirect("/validator")

# ==================================================
# VALIDATOR LOGOUT
# ==================================================

@app.route("/validator-logout")
def validator_logout():

    session.clear()

    return redirect(url_for("validator_login"))

# ==================================================
# DEPARTMENT LOGIN
# ==================================================

@app.route(
    "/department-login",
    methods=["GET", "POST"]
)
def department_login():

    error = None
    selected_department = ""

    if request.method == "POST":

        selected_department = request.form.get(
            "department",
            ""
        ).strip()

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if selected_department not in VALID_DEPARTMENTS:

            error = "Please select a valid department."

        else:

            user = authenticate_user(
                username,
                password,
                expected_role="department"
            )

            if (
                user
                and user.get("department") == selected_department
            ):

                session.clear()
                session.permanent = True

                session["department_logged_in"] = True
                session["department"] = user["department"]
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]

                return redirect(
                    url_for(
                        "department_dashboard",
                        department=user["department"]
                    )
                )

            error = (
                "Invalid username or password for the selected "
                "department, or your account is inactive."
            )

    return render_template(
        "department_login.html",
        departments=list(VALID_DEPARTMENTS),
        error=error,
        selected_department=selected_department
    )

# ==================================================
# DEPARTMENT DASHBOARD
# ==================================================

@app.route("/department/<department>")
def department_dashboard(department):

    if (
        not session.get("department_logged_in")
        or session.get("role") != "department"
    ):

        return redirect(url_for("department_login"))

    logged_department = session.get("department")

    # Prevent access to another department.
    if logged_department != department:

        return redirect(
            url_for(
                "department_dashboard",
                department=logged_department
            )
        )

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
# START DEPARTMENT REVIEW
# ==================================================

@app.route(
    "/department/review/<complaint_id>",
    methods=["POST"]
)
def start_review(complaint_id):

    if (
        not session.get("department_logged_in")
        or session.get("role") != "department"
    ):

        return redirect(url_for("department_login"))

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
# MARK COMPLAINT AS RESOLVED
# ==================================================

@app.route(
    "/department/resolve/<complaint_id>",
    methods=["POST"]
)
def resolve_complaint(complaint_id):

    if (
        not session.get("department_logged_in")
        or session.get("role") != "department"
    ):

        return redirect(url_for("department_login"))

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

@app.route("/department-logout")
def department_logout():

    session.clear()

    return redirect(url_for("department_login"))

# ==================================================
# ADMIN LOGIN
# ==================================================

@app.route(
    "/admin-login",
    methods=["GET", "POST"]
)
def admin_login():

    error = None

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = authenticate_user(
            username,
            password,
            expected_role="admin"
        )

        if user:

            session.clear()
            session.permanent = True

            session["admin_logged_in"] = True
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            return redirect(url_for("admin_dashboard"))

        error = (
            "Invalid username or password, "
            "or your account is inactive."
        )

    return render_template(
        "admin_login.html",
        error=error
    )

# ==================================================
# ADMIN DASHBOARD
# ==================================================

@app.route("/admin")
def admin_dashboard():

    if (
        not session.get("admin_logged_in")
        or session.get("role") != "admin"
    ):

        return redirect(url_for("admin_login"))

    connection = get_db_connection()

    # TOTAL COMPLAINTS

    total = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM complaints
        """
    ).fetchone()["count"]

    # ASSIGNED COMPLAINTS

    assigned = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = ?
        """,
        ("Assigned",)
    ).fetchone()["count"]

    # UNDER REVIEW

    under_review = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = ?
        """,
        ("Under Review",)
    ).fetchone()["count"]

    # RESOLVED

    resolved = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = ?
        """,
        ("Resolved",)
    ).fetchone()["count"]

    # FLAGGED

    flagged = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = ?
        """,
        ("Flagged for Review",)
    ).fetchone()["count"]

    # REJECTED

    rejected = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM complaints
        WHERE status = ?
        """,
        ("Rejected",)
    ).fetchone()["count"]

    # DEPARTMENT SUMMARY

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

    # RECENT COMPLAINTS

    recent_complaints = connection.execute(
        """
        SELECT
            complaint_id,
            category,
            department,
            location,
            status,
            date
        FROM complaints
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

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
        recent_complaints=recent_complaints
    )

# ==================================================
# ADMIN LOGOUT
# ==================================================

@app.route("/admin-logout")
def admin_logout():

    session.clear()

    return redirect(url_for("admin_login"))

# ==================================================
# START APPLICATION
# ==================================================

if __name__ == "__main__":

    create_database()

    upgrade_database()

    app.run(
        debug=os.environ.get("FLASK_DEBUG", "0") == "1"
    )