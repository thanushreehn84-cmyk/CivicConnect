"""
Civic Connect - Complaint Validation Service

Automatic checks (transparent and rule-based, no trained model):
  - Spam / gibberish patterns
  - Possible duplicate of an active complaint
  - Selected category does not match the description
  - Missing image/video evidence

Scoring: spam +60, duplicate +50, category mismatch +20, no evidence +10.
A score of 50 or more is sent to the validator queue.
"""

import json
import re
from datetime import datetime

from database.db import get_db_connection, add_history
from services.duplicate_service import find_possible_duplicates
from ai import (
    classify_complaint,
    predict_priority,
    get_supported_categories,
    summarize_complaint
)

VALID_STATUSES = {
    "Flagged for Review",
    "Assigned",
    "Rejected",
    "Under Review",
    "Resolved",
}

STATUS_FLAGGED = "Flagged for Review"
STATUS_ASSIGNED = "Assigned"
STATUS_REJECTED = "Rejected"

SCORE_SPAM = 60
SCORE_DUPLICATE = 50
SCORE_CATEGORY_MISMATCH = 20
SCORE_NO_EVIDENCE = 10
FLAG_THRESHOLD = 50

CATEGORY_CONFIDENCE_THRESHOLD = 0.6

MIN_REJECTION_REASON_LENGTH = 10
MAX_REJECTION_REASON_LENGTH = 500


# ==================================================
# FIELD VALIDATION
# ==================================================

def validate_date(date_text):
    """Valid YYYY-MM-DD date that is not in the future."""

    try:
        complaint_date = datetime.strptime(
            date_text,
            "%Y-%m-%d"
        ).date()

        return complaint_date <= datetime.now().date()

    except (ValueError, TypeError):
        return False


def validate_location(location):
    """Location must be understandable: 5+ characters with a letter/digit."""

    if not location:
        return False

    location = location.strip()

    if len(location) < 5:
        return False

    return bool(re.search(r"[A-Za-z0-9]", location))


def validate_description(description):
    """Description needs at least 20 characters and 5 words."""

    if not description:
        return False

    description = description.strip()

    if len(description) < 20:
        return False

    return len(description.split()) >= 5


# ==================================================
# SPAM DETECTION
# ==================================================

SPAM_PHRASES = (
    "asdf",
    "qwerty",
    "test complaint",
    "hello hello",
    "abc abc",
    "fake complaint",
)

_REPEATED_CHARACTER = re.compile(r"(.)\1{6,}")
_WEB_LINK = re.compile(r"(https?://|www\.)", re.IGNORECASE)
_LONG_CONSONANT_RUN = re.compile(r"[bcdfghjklmnpqrstvwxz]{7,}")
_HAS_VOWEL = re.compile(r"[aeiouy]")


def detect_spam(description):
    """Return a list of spam indicators. Empty list means none found."""

    text = (description or "").strip().lower()

    if not text:
        return []

    reasons = []

    if any(phrase in text for phrase in SPAM_PHRASES):
        reasons.append("contains placeholder or test wording")

    if _REPEATED_CHARACTER.search(text):
        reasons.append("contains a long run of repeated characters")

    words = re.findall(r"[a-z]+", text)

    if len(words) >= 8 and len(set(words)) / len(words) < 0.4:
        reasons.append("repeats the same words")

    if _WEB_LINK.search(text):
        reasons.append("contains a web link")

    unreadable = [
        word for word in words
        if len(word) >= 5
        and (
            not _HAS_VOWEL.search(word)
            or _LONG_CONSONANT_RUN.search(word)
        )
    ]

    if words and (
        len(unreadable) >= 2
        or len(unreadable) / len(words) >= 0.3
    ):
        reasons.append("contains unreadable text")

    return reasons


def is_spam(description):
    return bool(detect_spam(description))


# ==================================================
# CATEGORY CHECK
# ==================================================

def check_category(category, description):
    """Compare the citizen's category with the classifier's suggestion."""

    result = {
        "mismatch": False,
        "suggested_category": None,
        "confidence": 0.0,
    }

    if category not in get_supported_categories():
        return result

    prediction = classify_complaint(description)
    suggested = prediction["category"]
    confidence = prediction["confidence"]

    result["confidence"] = confidence

    if (
        suggested in get_supported_categories()
        and suggested != category
        and confidence >= CATEGORY_CONFIDENCE_THRESHOLD
    ):
        result["mismatch"] = True
        result["suggested_category"] = suggested

    return result


# ==================================================
# SUSPICION SCORE
# ==================================================

def calculate_suspicion_score(
    duplicate=False,
    spam=False,
    has_evidence=True,
    category_mismatch=False,
    duplicate_match=None,
    spam_reasons=None,
    selected_category=None,
    suggested_category=None,
):
    """Calculate complaint suspicion score and validation reasons."""

    score = 0
    messages = []
    reasons = []

    if duplicate:
        score += SCORE_DUPLICATE
        messages.append("Possible duplicate complaint.")

        if duplicate_match:
            percent = round(duplicate_match["similarity"] * 100)
            reasons.append(
                "Possible duplicate of "
                f"{duplicate_match['complaint_id']} "
                f"({percent}% similar)"
            )
        else:
            reasons.append("Possible duplicate complaint")

    if spam:
        score += SCORE_SPAM
        messages.append("Possible spam content.")

        if spam_reasons:
            reasons.append("Possible spam: " + "; ".join(spam_reasons))
        else:
            reasons.append("Possible spam content")

    if category_mismatch:
        score += SCORE_CATEGORY_MISMATCH
        messages.append("Category may not match the description.")

        if suggested_category and selected_category:
            reasons.append(
                f"Description looks like '{suggested_category}' "
                f"but was filed under '{selected_category}'"
            )
        else:
            reasons.append("Category may not match the description")

    if not has_evidence:
        score += SCORE_NO_EVIDENCE
        messages.append("No supporting evidence provided.")
        reasons.append("No image or video evidence attached")

    score = min(score, 100)

    status = STATUS_FLAGGED if score >= FLAG_THRESHOLD else STATUS_ASSIGNED

    message = " ".join(messages)

    if not message:
        message = (
            "Complaint passed automatic validation "
            "and was assigned to the concerned department."
        )

    return {
        "suspicion_score": score,
        "status": status,
        "validation_message": message,
        "messages": messages,
        "reasons": reasons,
    }


def analyze_complaint(category, location, description, has_evidence):
    """Run every automatic check for a new complaint."""

    matches = find_possible_duplicates(
        description=description,
        location=location,
        category=category,
        threshold=0.75
    )

    duplicate_match = None

    if matches:
        top = matches[0]
        duplicate_match = {
            "complaint_id": top["complaint"]["complaint_id"],
            "similarity": top["similarity"],
        }

    spam_reasons = detect_spam(description)
    category_result = check_category(category, description)

    result = calculate_suspicion_score(
        duplicate=bool(matches),
        spam=bool(spam_reasons),
        has_evidence=has_evidence,
        category_mismatch=category_result["mismatch"],
        duplicate_match=duplicate_match,
        spam_reasons=spam_reasons,
        selected_category=category,
        suggested_category=category_result["suggested_category"],
    )

    result["validation_reasons"] = json.dumps(result["reasons"])
    result["duplicate_of"] = (
        duplicate_match["complaint_id"] if duplicate_match else None
    )
    result["duplicate_similarity"] = (
        duplicate_match["similarity"] if duplicate_match else None
    )
    result["suggested_category"] = category_result["suggested_category"]

    return result


# ==================================================
# VALIDATOR QUEUE
# ==================================================

def get_complaint_for_validation(complaint_id):
    """Fetch a complaint using its public complaint ID."""

    if not complaint_id:
        return None

    connection = get_db_connection()

    try:
        complaint = connection.execute(
            "SELECT * FROM complaints WHERE complaint_id = ?",
            (complaint_id,)
        ).fetchone()

        return dict(complaint) if complaint else None

    finally:
        connection.close()


def get_flagged_complaints():
    """Highest suspicion first; oldest first among equal scores."""

    connection = get_db_connection()

    try:
        complaints = connection.execute(
            """
            SELECT *
            FROM complaints
            WHERE status = ?
            ORDER BY suspicion_score DESC, id ASC
            """,
            (STATUS_FLAGGED,)
        ).fetchall()

        return [dict(row) for row in complaints]

    finally:
        connection.close()


def _file_name(path):
    if not path:
        return None

    return path.replace("\\", "/").rsplit("/", 1)[-1]


def _score_level(score):
    score = score or 0

    if score >= 80:
        return "high"

    if score >= 50:
        return "medium"

    return "low"


def _legacy_reasons(validation_message):
    """Split an old plain-text validation message into reasons."""

    reasons = []

    for part in (validation_message or "").split(". "):
        part = part.strip().rstrip(".").strip()

        if part:
            reasons.append(part)

    return reasons


def build_review_item(complaint, originals=None):
    """Prepare a complaint row with a complete Explainable AI report."""

    item = dict(complaint)

    # 1. VALIDATION REASONS

    reasons = []

    if item.get("validation_reasons"):
        try:
            reasons = list(json.loads(item["validation_reasons"]))
        except (ValueError, TypeError):
            reasons = []

    if not reasons:
        reasons = _legacy_reasons(
            item.get("validation_message")
        )

    item["flag_reasons"] = reasons

    # 2. SUSPICION SCORE

    item["score_level"] = _score_level(
        item.get("suspicion_score")
    )

    # 3. EVIDENCE FILES

    item["image_file"] = _file_name(
        item.get("image_path")
    )

    item["video_file"] = _file_name(
        item.get("video_path")
    )

    # 4. AI CATEGORY CLASSIFICATION

    description = item.get("description", "") or ""
    location = item.get("location", "") or ""
    selected_category = item.get("category", "") or ""

    classification = classify_complaint(
        description,
        location
    )

    predicted_category = classification.get(
        "category",
        "Needs manual review"
    )

    confidence = classification.get(
        "confidence",
        0
    ) or 0

    # 5. AI PRIORITY PREDICTION

    priority = predict_priority(
        description,
        selected_category,
        location
    )

    predicted_priority = priority.get(
        "priority",
        "Low"
    )

    # 6. AI COMPLAINT SUMMARY

    summary = summarize_complaint(description)

    # 7. COMPLETE AI REPORT

    item["ai_report"] = {
        "predicted_category": predicted_category,
        "category_confidence": confidence,
        "confidence_percent": round(confidence * 100),
        "category_matches": predicted_category == selected_category,
        "matched_keywords": classification.get("matched_keywords", []),
        "category_scores": classification.get("scores", {}),
        "classification_method": classification.get(
            "method",
            "rule_based"
        ),
        "priority": predicted_priority,
        "priority_score": priority.get("score", 0),
        "priority_explanation": priority.get(
            "explanation",
            "No explanation available."
        ),
        "priority_indicators": priority.get("matched_indicators", []),
        "summary": summary.get("summary", "No summary available."),
        "summary_method": summary.get(
            "method",
            "extractive_rule_based"
        )
    }

    # 8. DUPLICATE COMPLAINT DETAILS

    item["duplicate"] = None

    if item.get("duplicate_of"):

        original = (originals or {}).get(
            item["duplicate_of"]
        )

        similarity = item.get("duplicate_similarity") or 0

        item["duplicate"] = {
            "complaint_id": item["duplicate_of"],
            "similarity_percent": round(similarity * 100),
            "original": original
        }

    # 9. BACKWARD-COMPATIBLE TEMPLATE FIELDS

    item["ai_classification"] = classification
    item["ai_predicted_category"] = predicted_category

    item["ai_confidence_percent"] = round(
        confidence * 100
    )

    item["ai_category_matches"] = (
        predicted_category == selected_category
    )

    item["ai_matched_keywords"] = classification.get(
        "matched_keywords",
        []
    )

    item["ai_category_scores"] = classification.get(
        "scores",
        {}
    )

    item["priority"] = predicted_priority

    item["priority_score"] = priority.get(
        "score",
        0
    )

    item["priority_explanation"] = priority.get(
        "explanation",
        "No explanation available."
    )

    item["priority_indicators"] = priority.get(
        "matched_indicators",
        []
    )

    return item


# ==================================================
# MISSING FUNCTION: GET REVIEW QUEUE
# ==================================================

def get_review_queue():
    """
    Fetch flagged complaints, retrieve possible original complaints,
    and prepare complete AI-assisted review items.
    """

    complaints = get_flagged_complaints()

    if not complaints:
        return []

    duplicate_ids = {
        complaint.get("duplicate_of")
        for complaint in complaints
        if complaint.get("duplicate_of")
    }

    originals = {}

    if duplicate_ids:

        connection = get_db_connection()

        try:
            placeholders = ",".join(
                "?" for _ in duplicate_ids
            )

            rows = connection.execute(
                f"""
                SELECT *
                FROM complaints
                WHERE complaint_id IN ({placeholders})
                """,
                tuple(duplicate_ids)
            ).fetchall()

            originals = {
                row["complaint_id"]: dict(row)
                for row in rows
            }

        finally:
            connection.close()

    review_queue = []

    for complaint in complaints:

        review_item = build_review_item(
            complaint,
            originals
        )

        review_queue.append(review_item)

    return review_queue


# ==================================================
# RECENTLY REVIEWED COMPLAINTS
# ==================================================

def get_recently_reviewed(limit=10):
    """Most recent validator decisions."""

    connection = get_db_connection()

    try:
        rows = connection.execute(
            """
            SELECT complaint_id, category, status, reviewed_by,
                   reviewed_at, rejection_reason
            FROM complaints
            WHERE reviewed_at IS NOT NULL
            ORDER BY reviewed_at DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


# ==================================================
# VALIDATOR DASHBOARD STATISTICS
# ==================================================

def get_review_stats():
    """Counts shown at the top of the validator dashboard."""

    today = datetime.now().date().isoformat() + "%"

    connection = get_db_connection()

    try:
        pending = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM complaints
            WHERE status = ?
            """,
            (STATUS_FLAGGED,)
        ).fetchone()["total"]

        approved_today = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM complaints
            WHERE reviewed_at LIKE ?
            AND rejection_reason IS NULL
            """,
            (today,)
        ).fetchone()["total"]

        rejected_today = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM complaints
            WHERE reviewed_at LIKE ?
            AND rejection_reason IS NOT NULL
            """,
            (today,)
        ).fetchone()["total"]

        return {
            "pending": pending,
            "approved_today": approved_today,
            "rejected_today": rejected_today,
        }

    finally:
        connection.close()


# ==================================================
# VALIDATOR DECISION
# ==================================================

def update_validation_decision(
    complaint_id,
    decision,
    validator="Validator",
    remarks=None
):
    """
    Approve (-> Assigned) or reject (-> Rejected) a flagged complaint.
    """

    if not complaint_id:
        raise ValueError("Complaint ID is required.")

    decision = str(decision).strip().lower()

    decisions = {
        "approve": STATUS_ASSIGNED,
        "approved": STATUS_ASSIGNED,
        "assign": STATUS_ASSIGNED,
        "reject": STATUS_REJECTED,
        "rejected": STATUS_REJECTED,
    }

    if decision not in decisions:
        raise ValueError("Decision must be approve or reject.")

    new_status = decisions[decision]

    remarks = (remarks or "").strip()
    rejection_reason = None

    if new_status == STATUS_REJECTED:

        if len(remarks) < MIN_REJECTION_REASON_LENGTH:
            raise ValueError(
                "A rejection reason of at least "
                f"{MIN_REJECTION_REASON_LENGTH} characters is required."
            )

        remarks = remarks[:MAX_REJECTION_REASON_LENGTH]
        rejection_reason = remarks

    connection = get_db_connection()

    try:
        cursor = connection.execute(
            """
            UPDATE complaints
            SET status = ?,
                rejection_reason = ?,
                reviewed_by = ?,
                reviewed_at = ?
            WHERE complaint_id = ?
            AND status = ?
            """,
            (
                new_status,
                rejection_reason,
                validator,
                datetime.now().isoformat(),
                complaint_id,
                STATUS_FLAGGED,
            )
        )

        if cursor.rowcount == 0:
            connection.rollback()
            return False

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    if new_status == STATUS_ASSIGNED:
        history_remarks = (
            remarks or
            "Complaint validated and assigned to the concerned department."
        )
    else:
        history_remarks = "Complaint rejected. Reason: " + remarks

    add_history(
        complaint_id,
        new_status,
        "Validator",
        history_remarks
    )

    return True


# ==================================================
# VALIDATION SUMMARY
# ==================================================

def get_validation_summary():
    """Return counts of complaints by validation status."""

    connection = get_db_connection()

    try:
        summary = {}

        for status in (
            STATUS_FLAGGED,
            STATUS_ASSIGNED,
            STATUS_REJECTED
        ):

            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM complaints
                WHERE status = ?
                """,
                (status,)
            ).fetchone()

            summary[status] = row["total"]

        return summary

    finally:
        connection.close()