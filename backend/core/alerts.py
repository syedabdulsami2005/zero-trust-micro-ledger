"""
Structured alert generation with full lifecycle support.

Creates alert objects from verification failures. Every critical
failure becomes a structured alert (Rule 7).

Lifecycle states:
  - active       : newly created, unresolved
  - acknowledged : user has seen it; chain still broken
  - resolved     : backend verified clean; incident closed

Severity mapping:
  - critical : hash_mismatch, previous_hash_mismatch (actual tampering)
  - warning  : index_gap, index_duplicate, truncation, segment_inconsistency
  - info     : schema_invalid
"""

from backend.core.normalizer import _normalize_timestamp
from backend.core.verifier import FailureType, VerificationFailure


# Severity mapping
_SEVERITY_MAP: dict[FailureType, str] = {
    FailureType.HASH_MISMATCH: "critical",
    FailureType.PREVIOUS_HASH_MISMATCH: "critical",
    FailureType.INDEX_GAP: "warning",
    FailureType.INDEX_DUPLICATE: "warning",
    FailureType.TRUNCATION: "warning",
    FailureType.SEGMENT_INCONSISTENCY: "warning",
    FailureType.SCHEMA_INVALID: "info",
}

# Alert type mapping
_ALERT_TYPE_MAP: dict[FailureType, str] = {
    FailureType.HASH_MISMATCH: "chain_break",
    FailureType.PREVIOUS_HASH_MISMATCH: "chain_break",
    FailureType.INDEX_GAP: "chain_break",
    FailureType.INDEX_DUPLICATE: "chain_break",
    FailureType.TRUNCATION: "truncation",
    FailureType.SEGMENT_INCONSISTENCY: "segment_error",
    FailureType.SCHEMA_INVALID: "schema_violation",
}

import itertools

# Thread-safe monotonic alert ID counter
_alert_counter = itertools.count(1)


def _next_alert_id() -> str:
    """Generate a monotonically increasing alert ID."""
    return f"alt-{next(_alert_counter):06d}"


def reset_alert_counter(value: int = 0) -> None:
    """Reset the alert counter.  Intended for testing only."""
    global _alert_counter
    _alert_counter = itertools.count(value + 1)


def make_incident_key(block_index: int | None, failure_type: str) -> str:
    """
    Build a stable deduplication key for an incident.

    Parameters
    ----------
    block_index : int | None
        The ledger block index involved (None for chain-level failures).
    failure_type : str
        The failure type string (e.g. ``"hash_mismatch"``).

    Returns
    -------
    str
        A deterministic key such as ``"block-7-hash_mismatch"`` or
        ``"chain-truncation"``.
    """
    if block_index is not None:
        return f"block-{block_index}-{failure_type}"
    return f"chain-{failure_type}"


def create_alert(
    failure: VerificationFailure,
    verification_id: str,
) -> dict:
    """
    Create a structured alert dict from a verification failure.

    The returned dict includes the full lifecycle scaffold:
    status, timestamps, incident_key, and occurrence fields.

    Parameters
    ----------
    failure : VerificationFailure
        The failure to convert into an alert.
    verification_id : str
        The verification run that produced this failure.

    Returns
    -------
    dict
        Alert record ready for storage.
    """
    now = _normalize_timestamp(None)
    failure_type_str = failure.failure_type.value
    incident_key = make_incident_key(failure.block_index, failure_type_str)

    # Extract hashes from details for quick access
    stored_hash = failure.details.get("stored")
    recomputed_hash = failure.details.get("recomputed")

    return {
        "alert_id": _next_alert_id(),
        # Lifecycle
        "status": "active",
        "created_at": now,
        "acknowledged_at": None,
        "resolved_at": None,
        # Deduplication
        "incident_key": incident_key,
        "occurrence_count": 1,
        "last_seen_at": now,
        # Classification
        "severity": _SEVERITY_MAP.get(failure.failure_type, "info"),
        "alert_type": _ALERT_TYPE_MAP.get(failure.failure_type, "unknown"),
        "failure_type": failure_type_str,
        "block_index": failure.block_index,
        "message": failure.message,
        # Evidence
        "stored_hash": stored_hash,
        "recomputed_hash": recomputed_hash,
        "details": {
            "block_index": failure.block_index,
            "failure_type": failure_type_str,
            **failure.details,
        },
        "verification_id": verification_id,
        # Legacy compat field
        "timestamp_utc": now,
        "acknowledged": False,
    }


def create_alerts_from_result(result) -> list[dict]:
    """
    Create alert dicts for every failure in a VerificationResult.

    Parameters
    ----------
    result : VerificationResult
        The verification result to process.

    Returns
    -------
    list[dict]
        One alert per failure.
    """
    return [create_alert(failure, result.verification_id) for failure in result.failures]
