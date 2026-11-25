
"""
Civic Connect - Validator Routes

Handles complaint verification and validation decisions.
"""

from functools import wraps

from flask import Blueprint, jsonify, request, session

from services.validation_service import (
    get_flagged_complaints,
    get_complaint_for_validation,
    update_validation_decision,
    get_validation_summary,
)


validator_bp = Blueprint(
    "validator",
    __name__,
    url_prefix="/validator"
)


def validator_required(function):
    """Allow access only to authenticated validators."""

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return jsonify({
                "success": False,
                "message": "Please log in first."
            }), 401

        if session.get("role") != "validator":
            return jsonify({
                "success": False,
                "message": "Validator access required."
            }), 403

        return function(*args, **kwargs)

    return decorated_function


@validator_bp.route("/complaints", methods=["GET"])
@validator_required
def flagged_complaints():
    """List complaints awaiting manual validation."""

    complaints = get_flagged_complaints()

    return jsonify({
        "success": True,
        "total": len(complaints),
        "complaints": complaints,
    })


@validator_bp.route(
    "/complaints/<string:complaint_id>",
    methods=["GET"]
)
@validator_required
def complaint_details(complaint_id):
    """Get a complaint for validator review."""

    complaint = get_complaint_for_validation(complaint_id)

    if complaint is None:
        return jsonify({
            "success": False,
            "message": "Complaint not found."
        }), 404

    return jsonify({
        "success": True,
        "complaint": complaint,
    })


@validator_bp.route(
    "/complaints/<string:complaint_id>/decision",
    methods=["POST"]
)
@validator_required
def validate_complaint(complaint_id):
    """Approve or reject a flagged complaint."""

    data = request.get_json(silent=True) or {}

    decision = data.get("decision", "")
    remarks = data.get("remarks", "")

    validator = session.get("username", "Validator")

    try:
        updated = update_validation_decision(
            complaint_id=complaint_id,
            decision=decision,
            validator=validator,
            remarks=remarks,
        )

        if not updated:
            return jsonify({
                "success": False,
                "message": (
                    "Complaint not found or it is no longer "
                    "awaiting validation."
                )
            }), 409

        return jsonify({
            "success": True,
            "message": "Validation decision saved successfully.",
            "complaint_id": complaint_id,
            "decision": decision,
        })

    except ValueError as error:
        return jsonify({
            "success": False,
            "message": str(error)
        }), 400


@validator_bp.route("/summary", methods=["GET"])
@validator_required
def validation_summary():
    """Return complaint validation statistics."""

    summary = get_validation_summary()

    return jsonify({
        "success": True,
        "summary": summary,
    })
