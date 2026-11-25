
"""
Civic Connect - AI Complaint Classifier

Classifies civic complaints into the categories supported by the portal.
This is a transparent rule-based baseline, not a trained machine-learning
model. It can later be replaced or enhanced with a trained NLP model.
"""

import re
from collections import defaultdict


CATEGORY_KEYWORDS = {
    "Illegal Construction": {
        "construction", "illegal building", "unauthorized building",
        "encroachment", "building violation", "demolition",
        "unauthorized construction", "occupied footpath",
        "blocked footpath", "illegal structure"
    },
    "Environmental Issue": {
        "pollution", "garbage", "waste", "dumping", "sewage",
        "smoke", "toxic", "contamination", "dirty water",
        "air pollution", "water pollution", "open burning",
        "plastic waste", "tree cutting", "noise pollution"
    },
    "Traffic Issue": {
        "traffic", "signal", "accident", "road", "pothole",
        "parking", "congestion", "speeding", "footpath",
        "broken streetlight", "road damage", "illegal parking",
        "blocked road", "traffic jam"
    },
    "Public Safety": {
        "unsafe", "danger", "harassment", "theft", "violence",
        "threat", "crime", "assault", "fire", "exposed wire",
        "open manhole", "fallen electric wire", "public safety",
        "street light not working"
    }
}


def _normalize_text(text):
    """Normalize complaint text for consistent keyword matching."""
    if not isinstance(text, str):
        return ""

    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text)


def classify_complaint(description, location=""):
    """
    Classify a complaint using weighted keyword matching.

    Returns:
        {
            "category": str,
            "confidence": float,
            "scores": dict,
            "matched_keywords": list,
            "method": str
        }

    A low-confidence result is marked as 'Needs manual review'
    rather than being presented as a certain prediction.
    """
    text = _normalize_text(f"{description or ''} {location or ''}")

    if not text:
        return {
            "category": "Needs manual review",
            "confidence": 0.0,
            "scores": {category: 0.0 for category in CATEGORY_KEYWORDS},
            "matched_keywords": [],
            "method": "rule_based"
        }

    scores = defaultdict(float)
    matched = defaultdict(list)

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            normalized_keyword = _normalize_text(keyword)

            if not normalized_keyword:
                continue

            # Match complete phrases/words, not partial substrings.
            pattern = r"\b" + re.escape(normalized_keyword) + r"\b"

            if re.search(pattern, text):
                # Multi-word phrases provide stronger evidence.
                weight = 2.0 if " " in normalized_keyword else 1.0
                scores[category] += weight
                matched[category].append(keyword)

    all_scores = {
        category: round(scores[category], 2)
        for category in CATEGORY_KEYWORDS
    }

    ranked = sorted(
        all_scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    best_category, best_score = ranked[0]
    total_score = sum(all_scores.values())

    if best_score == 0:
        return {
            "category": "Needs manual review",
            "confidence": 0.0,
            "scores": all_scores,
            "matched_keywords": [],
            "method": "rule_based"
        }

    confidence = best_score / total_score

    # Require both a minimum score and a clear winning category.
    if best_score < 1 or confidence < 0.50:
        predicted_category = "Needs manual review"
    else:
        predicted_category = best_category

    return {
        "category": predicted_category,
        "confidence": round(confidence, 3),
        "scores": all_scores,
        "matched_keywords": matched[best_category],
        "method": "rule_based"
    }


def get_supported_categories():
    """Return the categories supported by the complaint portal."""
    return list(CATEGORY_KEYWORDS.keys())
