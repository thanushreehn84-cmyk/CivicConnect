
"""
Civic Connect - Admin Routes

Handles administrator access and staff management.
"""

from functools import wraps

from flask import Blueprint, jsonify, request, session

from services.auth_service import (
    create_staff_account,
    get_all_staff,
    set_user_active_status,
    change_user_password,
)


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(function):
    """Allow access only to authenticated administrators."""

    @wraps(function)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({
                "success": False,
                "message": "Please log in first."
            }), 401

        if session.get("role") != "admin":
            return jsonify({
                "success": False,
                "message": "Administrator access required."
            }), 403

        return function(*args, **kwargs)

    return decorated_function


@admin_bp.route("/staff", methods=["GET"])
@admin_required
def staff_list():
    """Return all staff accounts."""

    staff = get_all_staff()

    return jsonify({
        "success": True,
        "staff": staff
    })


@admin_bp.route("/staff", methods=["POST"])
@admin_required
def create_staff():
    """Create a validator or department staff account."""

    data = request.get_json(silent=True) or request.form

    try:
        username = data.get("username", "")
        password = data.get("password", "")
        role = data.get("role", "")
        department = data.get("department")

        user_id = create_staff_account(
            username=username,
            password=password,
            role=role,
            department=department,
        )

        return jsonify({
            "success": True,
            "message": "Staff account created successfully.",
            "user_id": user_id
        }), 201

    except ValueError as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 400

    except Exception:
        return jsonify({
            "success": False,
            "message": "Unable to create staff account."
        }), 500


@admin_bp.route("/staff/<int:user_id>/status", methods=["PATCH"])
@admin_required
def update_staff_status(user_id):
    """Activate or deactivate a staff account."""

    data = request.get_json(silent=True) or {}

    if "is_active" not in data:
        return jsonify({
            "success": False,
            "message": "is_active is required."
        }), 400

    try:
        value = data["is_active"]

        if not isinstance(value, bool):
            return jsonify({
                "success": False,
                "message": "is_active must be true or false."
            }), 400

        updated = set_user_active_status(user_id, value)

        if not updated:
            return jsonify({
                "success": False,
                "message": "User not found or status unchanged."
            }), 404

        return jsonify({
            "success": True,
            "message": "Staff status updated successfully."
        })

    except ValueError as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 400


@admin_bp.route("/staff/<int:user_id>/password", methods=["PATCH"])
@admin_required
def update_staff_password(user_id):
    """Change a staff member's password."""

    data = request.get_json(silent=True) or {}
    new_password = data.get("new_password", "")

    try:
        updated = change_user_password(
            user_id,
            new_password
        )

        if not updated:
            return jsonify({
                "success": False,
                "message": "User not found."
            }), 404

        return jsonify({
            "success": True,
            "message": "Password updated successfully."
        })

    except ValueError as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 400
