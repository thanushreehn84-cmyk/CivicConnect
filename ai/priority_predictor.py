
"""
Civic Connect - Complaint Priority Predictor

Estimates complaint priority using transparent risk indicators.
This is a rule-based baseline and not a trained predictive model.
"""

import re


HIGH_RISK_KEYWORDS = {
    "fire", "accident", "injury", "injured", "emergency",
    "electrocution", "electric shock", "exposed wire",
    "open manhole", "collapse", "building collapse",
    "gas leak", "violence", "life threatening",
    "dangerous", "severe flooding"
}

MEDIUM_RISK_KEYWORDS = {
    "pothole", "sewage", "overflow", "blocked drain",
    "water leakage", "garbage", "streetlight",
    "traffic jam", "road damage", "pollution",
    "illegal dumping", "broken road"
}


def normalize_text(text):
    """Normalize text for keyword detection."""
    if not isinstance(text, str):
        return ""

    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text)


def predict_priority(description, category="", location=""):
    """
    Estimate priority based on complaint risk indicators.

    Returns:
        priority: Critical, High, Medium, or Low
        score: risk score from 0 to 100
        matched_indicators: detected risk indicators
        explanation: reason for the estimate
        method: rule_based
    """
    text = normalize_text(
        f"{description or ''} {category or ''} {location or ''}"
    )

    if not text.strip():
        return {
            "priority": "Low",
            "score": 0,
            "matched_indicators": [],
            "explanation": "Insufficient complaint information.",
            "method": "rule_based"
        }

    score = 0
    matched = []

    for keyword in HIGH_RISK_KEYWORDS:
        if re.search(r"\b" + re.escape(keyword) + r"\b", text):
            score += 25
            matched.append(keyword)

    for keyword in MEDIUM_RISK_KEYWORDS:
        if re.search(r"\b" + re.escape(keyword) + r"\b", text):
            score += 10
            matched.append(keyword)

    score = min(score, 100)

    if score >= 50:
        priority = "Critical"
    elif score >= 25:
        priority = "High"
    elif score >= 10:
        priority = "Medium"
    else:
        priority = "Low"

    if matched:
        explanation = (
            "Priority estimated from these detected indicators: "
            + ", ".join(sorted(matched))
        )
    else:
        explanation = (
            "No predefined high-risk indicators were detected."
        )

    return {
        "priority": priority,
        "score": score,
        "matched_indicators": sorted(matched),
        "explanation": explanation,
        "method": "rule_based"
    }
