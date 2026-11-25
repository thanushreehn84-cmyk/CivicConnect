
import sqlite3
from datetime import datetime

# Import the absolute database path from project settings.
from config.settings import DATABASE_NAME


def get_db_connection():

    connection = sqlite3.connect(DATABASE_NAME)

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def create_database():

    connection = get_db_connection()

    try:

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

        connection.execute("""
            CREATE TABLE IF NOT EXISTS complaint_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complaint_id TEXT NOT NULL,
                status TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                changed_by TEXT,
                remarks TEXT
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK(role IN ('admin', 'validator', 'department')),
                department TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        connection.commit()

    finally:
        connection.close()


def upgrade_database():

    connection = get_db_connection()

    try:

        columns = connection.execute(
            "PRAGMA table_info(complaints)"
        ).fetchall()

        existing_columns = {
            column["name"] for column in columns
        }

        required_columns = {
            "image_path": "TEXT",
            "video_path": "TEXT",
            "suspicion_score": "INTEGER DEFAULT 0",
            "validation_message": "TEXT",
            "created_at": "TEXT",
            "validation_reasons": "TEXT",
            "duplicate_of": "TEXT",
            "duplicate_similarity": "REAL",
            "suggested_category": "TEXT",
            "rejection_reason": "TEXT",
            "reviewed_by": "TEXT",
            "reviewed_at": "TEXT"
        }

        for column, datatype in required_columns.items():

            if column not in existing_columns:

                connection.execute(
                    f"ALTER TABLE complaints ADD COLUMN {column} {datatype}"
                )

        connection.execute("""
            CREATE TABLE IF NOT EXISTS complaint_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complaint_id TEXT NOT NULL,
                status TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                changed_by TEXT,
                remarks TEXT
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK(role IN ('admin', 'validator', 'department')),
                department TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        connection.commit()

    finally:
        connection.close()


def add_history(
    complaint_id,
    status,
    changed_by="System",
    remarks=""
):

    connection = get_db_connection()

    try:

        connection.execute("""
            INSERT INTO complaint_history (
                complaint_id,
                status,
                timestamp,
                changed_by,
                remarks
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            complaint_id,
            status,
            datetime.now().isoformat(),
            changed_by,
            remarks
        ))

        connection.commit()

    finally:
        connection.close()


def create_staff_user(
    username,
    password_hash,
    role,
    department=None
):

    username = username.strip()

    if not username:
        raise ValueError("Username is required.")

    if role not in ("admin", "validator", "department"):
        raise ValueError("Invalid user role.")

    if role == "validator":
        department = None

    connection = get_db_connection()

    try:

        cursor = connection.execute("""
            INSERT INTO users (
                username,
                password_hash,
                role,
                department,
                is_active,
                created_at
            )
            VALUES (?, ?, ?, ?, 1, ?)
        """, (
            username,
            password_hash,
            role,
            department,
            datetime.now().isoformat()
        ))

        connection.commit()

        return cursor.lastrowid

    except sqlite3.IntegrityError as error:

        connection.rollback()

        raise ValueError(
            "Username already exists."
        ) from error

    finally:
        connection.close()
