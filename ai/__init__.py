
"""
Civic Connect - AI Module

Centralizes AI-related functions for use across the application.
"""

from .classifier import (
    classify_complaint,
    get_supported_categories
)

from .duplicate_detector import (
    normalize_text,
    text_similarity,
    location_similarity,
    compare_complaints,
    find_duplicate_complaints
)

from .priority_predictor import (
    predict_priority
)

from .summarizer import (
    summarize_complaint,
    build_complaint_brief
)


__all__ = [
    "classify_complaint",
    "get_supported_categories",
    "normalize_text",
    "text_similarity",
    "location_similarity",
    "compare_complaints",
    "find_duplicate_complaints",
    "predict_priority",
    "summarize_complaint",
    "build_complaint_brief"
]
