
"""
Civic Connect - Department Routes

Handles department complaint management.
"""

from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request, session

from database.db import get_db_connection


department_bp = Blueprint(
    "department",
    __name__,
    url_prefix="/department"
)


def department_required(function):
    """Allow access only to logged-in department staff."""

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return jsonify({
                "success": False,
                "message": "Please log in first."
            }), 401

        if session.get("role") != "department":
            return jsonify({
                "success": False,
                "message": "Department access required."
            }), 403

        if not session.get("department"):
            return jsonify({
                "success": False,
                "message": "Department information is missing."
            }), 403

        return function(*args, **kwargs)

    return decorated_function


@department_bp.route("/complaints", methods=["GET"])
@department_required
def department_complaints():
    """Display complaints assigned to the logged-in department."""

    department_name = session.get("department")

    connection = get_db_connection()

    try:
        complaints = connection.execute(
            """
            SELECT
                complaint_id,
                category,
                location,
                date,
                description,
                status,
                created_at
            FROM complaints
            WHERE department = ?
            ORDER BY id DESC
            """,
            (department_name,)
        ).fetchall()

        return jsonify({
            "success": True,
            "department": department_name,
            "complaints": [dict(row) for row in complaints]
        })

    finally:
        connection.close()


@department_bp.route(
    "/complaints/<string:complaint_id>/status",
    methods=["PATCH"]
)
@department_required
def update_complaint_status(complaint_id):
    """Update the status of a complaint assigned to this department."""

    data = request.get_json(silent=True) or {}
    new_status = str(data.get("status", "")).strip()

    allowed_statuses = {
        "Under Review",
        "Resolved",
    }

    if new_status not in allowed_statuses:
        return jsonify({
            "success": False,
            "message": "Status must be Under Review or Resolved."
        }), 400

    department_name = session.get("department")
    changed_by = session.get("username", "Department Staff")
    remarks = str(data.get("remarks", "")).strip()

    connection = get_db_connection()

    try:
        complaint = connection.execute(
            """
            SELECT complaint_id, status
            FROM complaints
            WHERE complaint_id = ?
              AND department = ?
            """,
            (complaint_id, department_name)
        ).fetchone()

        if complaint is None:
            return jsonify({
                "success": False,
                "message": "Complaint not found in your department."
            }), 404

        if complaint["status"] not in {
            "Assigned",
            "Under Review",
        }:
            return jsonify({
                "success": False,
                "message": "This complaint cannot be updated from its current status."
            }), 409

        connection.execute(
            """
            UPDATE complaints
            SET status = ?
            WHERE complaint_id = ?
              AND department = ?
            """,
            (new_status, complaint_id, department_name)
        )

        connection.execute(
            """
            INSERT INTO complaint_history
                (complaint_id, status, timestamp, changed_by, remarks)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                complaint_id,
                new_status,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                changed_by,
                remarks or f"Status updated to {new_status}.",
            )
        )

        connection.commit()

        return jsonify({
            "success": True,
            "message": "Complaint status updated successfully.",
            "complaint_id": complaint_id,
            "status": new_status,
        })

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
