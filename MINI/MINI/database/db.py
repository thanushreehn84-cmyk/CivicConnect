import sqlite3
from datetime import datetime

def get_db_connection():

    connection = sqlite3.connect(
        "civicconnect.db"
    )

    connection.row_factory = sqlite3.Row

    return connection

def create_database():

    connection = get_db_connection()

    # COMPLAINTS TABLE

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
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','validator','department')),
            department TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    connection.commit()

    connection.close()

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

    # MAKE SURE HISTORY TABLE EXISTS

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

    connection.commit()

    connection.close()

def add_history(
    complaint_id,
    status,
    changed_by="System",
    remarks=""
):

    connection = get_db_connection()

    connection.execute(
        """
        INSERT INTO complaint_history
        (
            complaint_id,
            status,
            timestamp,
            changed_by,
            remarks
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            complaint_id,
            status,
            datetime.now().isoformat(),
            changed_by,
            remarks
        )
    )

    connection.commit()

    connection.close()
