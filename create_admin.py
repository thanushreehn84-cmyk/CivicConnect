
import getpass
from datetime import datetime

from werkzeug.security import generate_password_hash

from database.db import (
    create_database,
    upgrade_database,
    get_db_connection
)


def create_admin():

    print("\n================================")
    print("   CIVIC CONNECT - ADMIN SETUP")
    print("================================\n")

    create_database()
    upgrade_database()

    username = input("Enter administrator username: ").strip()

    if len(username) < 4:
        print("Username must contain at least 4 characters.")
        return

    password = getpass.getpass("Enter administrator password: ")
    confirm_password = getpass.getpass("Confirm administrator password: ")

    if len(password) < 12:
        print("Password must contain at least 12 characters.")
        return

    if password != confirm_password:
        print("Passwords do not match.")
        return

    connection = get_db_connection()

    try:
        existing_admin = connection.execute(
            "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()

        if existing_admin:
            print("\nAn administrator account already exists.")
            return

        connection.execute(
            """
            INSERT INTO users
            (username, password_hash, role, department,
             is_active, created_at)
            VALUES (?, ?, ?, NULL, 1, ?)
            """,
            (
                username,
                generate_password_hash(password),
                "admin",
                datetime.now().isoformat()
            )
        )

        connection.commit()

        print("\nAdministrator account created successfully!")
        print("You can now log in using your new credentials.")

    except Exception as error:
        connection.rollback()
        print("Account creation failed:", error)

    finally:
        connection.close()


if __name__ == "__main__":
    create_admin()
