
import getpass

from database.db import (
    create_database,
    upgrade_database,
    DATABASE_NAME
)

from services.auth_service import (
    create_staff_account
)


def main():

    print("\n======================================")
    print("       CIVICCONNECT")
    print("       VALIDATOR ACCOUNT SETUP")
    print("======================================")

    create_database()
    upgrade_database()

    print("\nDatabase location:")
    print(DATABASE_NAME)

    username = input(
        "\nEnter validator username: "
    ).strip()

    password = getpass.getpass(
        "Create password: "
    )

    confirm_password = getpass.getpass(
        "Confirm password: "
    )

    if password != confirm_password:

        print("\nERROR: Passwords do not match.")
        return

    try:

        create_staff_account(
            username=username,
            password=password,
            role="validator"
        )

        print("\n--------------------------------------")
        print("VALIDATOR ACCOUNT CREATED SUCCESSFULLY")
        print("--------------------------------------")

        print("Username:", username.lower())
        print("Role: validator")
        print("Status: Active")

        print("\nYou can now access the Validator Portal.")

    except ValueError as error:

        print("\nACCOUNT ERROR:", error)

    except Exception as error:

        print("\nSYSTEM ERROR:", error)


if __name__ == "__main__":
    main()
