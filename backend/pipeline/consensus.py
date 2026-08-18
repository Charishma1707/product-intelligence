"""
pipeline/consensus.py — Phase 2: Cross-document consensus scoring.

When the Detective Agent retrieves multiple documents for the same product,
this module compares the same field across all docs and applies a conflict
penalty to the confidence score.

Penalty Schedule (from architecture blueprint):
  -0.00  all docs agree
  -0.30  one conflict (2 distinct values)
  -0.50  major disagreement (3+ distinct values)
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_value(v: Any) -> str:
    """Normalize a value to a comparable string (strip whitespace, lowercase, remove units)."""
    if v is None:
        return ""
    s = str(v).lower().strip()
    # Normalize whitespace
    s = re.sub(r"\s+", " ", s)
    # Strip trailing unit noise for comparison (e.g. "7 a" == "7.0 a")
    s = re.sub(r"(\d)\.0\b", r"\1", s)
    return s


def compute_consensus_penalties(
    field_name: str,
    doc_extracted_values: list[Any],
) -> float:
    """
    Given a list of values extracted for the same field from different docs,
    return the confidence penalty (0.0 – 0.50) that should be applied.

    Args:
        field_name: The specification field (for logging)
        doc_extracted_values: List of extracted values (one per doc), may contain None

    Returns:
        Penalty float to SUBTRACT from confidence (0.0 = no conflict)
    """
    # Filter out None / empty values
    valid_values = [_normalize_value(v) for v in doc_extracted_values if v is not None]
    valid_values = [v for v in valid_values if v]

    if len(valid_values) <= 1:
        return 0.0  # Only one source — can't detect conflict

    unique = set(valid_values)

    if len(unique) == 1:
        logger.debug("Consensus '%s': all %d docs agree on %r", field_name, len(valid_values), list(unique)[0])
        return 0.0  # Perfect consensus

    if len(unique) == 2:
        logger.info(
            "Consensus '%s': conflict detected — values=%s → penalty -0.30",
            field_name, list(unique)
        )
        return 0.30  # One conflict

    logger.warning(
        "Consensus '%s': major disagreement — values=%s → penalty -0.50",
        field_name, list(unique)
    )
    return 0.50  # Major disagreement


def compute_all_consensus_penalties(
    field_names: list[str],
    per_doc_fields: list[dict[str, Any]],
) -> dict[str, float]:
    """
    Compute consensus penalties for all fields across multiple documents.

    Args:
        field_names: List of expected specification field names
        per_doc_fields: List of dicts, each dict = {field_name: value} for one doc

    Returns:
        dict[field_name → penalty float]
    """
    if len(per_doc_fields) <= 1:
        return {}  # No consensus possible with a single doc

    penalties: dict[str, float] = {}
    for fname in field_names:
        values = [doc.get(fname) for doc in per_doc_fields]
        penalty = compute_consensus_penalties(fname, values)
        if penalty > 0:
            penalties[fname] = penalty

    return penalties
