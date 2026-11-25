
"""
Civic Connect - Citizen Routes

Handles public complaint tracking.
"""

from flask import Blueprint, jsonify

from database.db import get_db_connection


citizen_bp = Blueprint(
    "citizen",
    __name__,
    url_prefix="/citizen"
)


@citizen_bp.route("/track/<string:complaint_id>", methods=["GET"])
def track_complaint(complaint_id):
    """Allow citizens to check the status of a complaint."""

    complaint_id = complaint_id.strip()

    if not complaint_id:
        return jsonify({
            "success": False,
            "message": "Complaint ID is required."
        }), 400

    connection = get_db_connection()

    try:
        complaint = connection.execute(
            """
            SELECT
                complaint_id,
                category,
                status,
                created_at
            FROM complaints
            WHERE complaint_id = ?
            """,
            (complaint_id,)
        ).fetchone()

        if complaint is None:
            return jsonify({
                "success": False,
                "message": "Complaint not found. Please check the complaint ID."
            }), 404

        return jsonify({
            "success": True,
            "complaint": dict(complaint)
        })

    finally:
        connection.close()
