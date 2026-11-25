
from datetime import datetime
import re
import sqlite3

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database.db import get_db_connection


VALID_ROLES = ("admin", "validator", "department")

VALID_DEPARTMENTS = (
    "Municipality",
    "Pollution Control",
    "Traffic Department",
    "Police"
)

MIN_PASSWORD_LENGTH = 12


def normalize_username(username):

    if not isinstance(username, str):
        return ""

    return username.strip().lower()


def validate_username(username):

    username = normalize_username(username)

    return bool(
        re.fullmatch(r"[a-z0-9._@-]{4,50}", username)
    )


def validate_password(password):

    if not isinstance(password, str):
        return False, "Invalid password."

    if len(password) < MIN_PASSWORD_LENGTH:
        return False, "Minimum 12 characters required."

    if not re.search(r"[A-Z]", password):
        return False, "At least one uppercase letter required."

    if not re.search(r"[a-z]", password):
        return False, "At least one lowercase letter required."

    if not re.search(r"[0-9]", password):
        return False, "At least one number required."

    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "At least one special character required."

    if re.search(r"\s", password):
        return False, "Spaces are not allowed."

    return True, "Password is valid."


def authenticate_user(username, password, expected_role=None):

    username = normalize_username(username)

    if not username or not isinstance(password, str) or not password:
        return None

    if expected_role and expected_role not in VALID_ROLES:
        return None

    connection = get_db_connection()

    try:

        user = connection.execute("""
            SELECT *
            FROM users
            WHERE LOWER(TRIM(username)) = ?
            AND is_active = 1
        """, (username,)).fetchone()

        if not user:
            return None

        if not check_password_hash(
            user["password_hash"],
            password
        ):
            return None

        if expected_role and user["role"] != expected_role:
            return None

        return dict(user)

    finally:
        connection.close()


def create_staff_account(
    username,
    password,
    role,
    department=None
):

    username = normalize_username(username)

    if not validate_username(username):
        raise ValueError(
            "Username must contain 4-50 valid characters."
        )

    if role not in ("validator", "department"):
        raise ValueError(
            "Only validator and department accounts can be created."
        )

    valid, message = validate_password(password)

    if not valid:
        raise ValueError(message)

    if role == "department":

        if department not in VALID_DEPARTMENTS:
            raise ValueError("Invalid department.")

    else:
        department = None

    password_hash = generate_password_hash(password)

    connection = get_db_connection()

    try:

        connection.execute("""
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

        return True

    except sqlite3.IntegrityError as error:

        connection.rollback()

        raise ValueError(
            "Username already exists. Use the existing account or reset its password."
        ) from error

    except Exception:

        connection.rollback()
        raise

    finally:
        connection.close()


def change_user_password(user_id, new_password):

    valid, message = validate_password(new_password)

    if not valid:
        raise ValueError(message)

    password_hash = generate_password_hash(new_password)

    connection = get_db_connection()

    try:

        cursor = connection.execute("""
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
        """, (password_hash, user_id))

        connection.commit()

        return cursor.rowcount > 0

    except Exception:

        connection.rollback()
        raise

    finally:
        connection.close()


def set_user_active_status(user_id, is_active):

    connection = get_db_connection()

    try:

        cursor = connection.execute("""
            UPDATE users
            SET is_active = ?
            WHERE id = ?
            AND role != 'admin'
        """, (
            1 if is_active else 0,
            user_id
        ))

        connection.commit()

        return cursor.rowcount > 0

    except Exception:

        connection.rollback()
        raise

    finally:
        connection.close()


def get_all_staff():

    connection = get_db_connection()

    try:

        users = connection.execute("""
            SELECT
                id,
                username,
                role,
                department,
                is_active,
                created_at
            FROM users
            WHERE role != 'admin'
            ORDER BY created_at DESC
        """).fetchall()

        return [dict(user) for user in users]

    finally:
        connection.close()
