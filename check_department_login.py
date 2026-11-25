
from getpass import getpass
from werkzeug.security import check_password_hash
from database.db import get_db_connection

username = input("Enter department username: ").strip().lower()
password = getpass("Enter department password: ")

connection = get_db_connection()

try:
    user = connection.execute(
        """
        SELECT id, username, password_hash, role, department, is_active
        FROM users
        WHERE LOWER(TRIM(username)) = ?
        """,
        (username,)
    ).fetchone()

    if not user:
        print("\nRESULT: USER NOT FOUND")
    else:
        print("\nACCOUNT FOUND")
        print("Username:", repr(user["username"]))
        print("Role:", user["role"])
        print("Department:", repr(user["department"]))
        print("Active:", user["is_active"])

        password_valid = check_password_hash(
            user["password_hash"],
            password
        )

        print("Password correct:", password_valid)
        print(
            "Role correct:",
            user["role"] == "department"
        )
        print(
            "Department correct:",
            user["department"] == "Municipality"
        )
        print(
            "Account active:",
            user["is_active"] == 1
        )

finally:
    connection.close()
