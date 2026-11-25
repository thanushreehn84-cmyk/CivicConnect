"""Create the first Civic Connect administrator interactively. Run once."""
import getpass
from datetime import datetime
from werkzeug.security import generate_password_hash
from database.db import create_database, upgrade_database, get_db_connection

def main():
    create_database(); upgrade_database()
    username = input("Initial admin username (4+ chars): ").strip()
    password = getpass.getpass("Admin password (12+ chars): ")
    confirm = getpass.getpass("Confirm password: ")
    if len(username) < 4 or len(password) < 12 or password != confirm:
        raise SystemExit("Invalid input: username must be 4+ chars, password 12+ chars, and passwords must match.")
    db = get_db_connection()
    if db.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        db.close(); raise SystemExit("An administrator already exists. Ask an existing admin to manage accounts.")
    db.execute("INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
               (username, generate_password_hash(password), "admin", datetime.now().isoformat()))
    db.commit(); db.close()
    print("Administrator account created. Keep the credentials secure.")
if __name__ == "__main__": main()
