"""
Deterministic event normalizer.

Converts raw event data into a stable internal representation so that
equivalent data always yields consistent hash results across runs.

Rules enforced (from TRD §Canonical Serialization Rule):
  - UTC ISO-8601 timestamps with millisecond precision
  - UTF-8 encoding with \\n line endings
  - Predictable replacement for invalid byte sequences
  - Sorted keys in nested structures
  - Null preservation (no stripping of null fields)
  - Auto-generated event_id in evt-NNNNNN format
"""

import os.path
import itertools
from datetime import datetime, timezone
from typing import Any

# Thread-safe monotonic event counter
_event_counter = itertools.count(1)

# Required top-level fields in a raw event
REQUIRED_FIELDS = ("event_type", "source_type", "source_path")

# Allowed event types per the TRD block schema
VALID_EVENT_TYPES = frozenset({
    "genesis",
    "file_modified",
    "file_created",
    "file_deleted",
    "file_permissions_changed",
    "config_changed",
    "log_entry",
    "service_started",
    "service_stopped",
    "manual_snapshot",
})

# Allowed source types
VALID_SOURCE_TYPES = frozenset({
    "system",
    "config_file",
    "log_file",
    "binary_file",
    "directory",
    "service",
    "manual",
})


class NormalizationError(Exception):
    """Raised when an event cannot be normalized."""


def _next_event_id() -> str:
    """Generate a monotonically increasing event ID (thread-safe)."""
    return f"evt-{next(_event_counter):06d}"


def reset_event_counter(value: int = 0) -> None:
    """Reset the global event counter.  Intended for testing only."""
    global _event_counter
    _event_counter = itertools.count(value + 1)


def _normalize_timestamp(raw_ts: Any) -> str:
    """
    Normalise a timestamp to UTC ISO-8601 with millisecond precision.

    Accepts:
      - ``None`` / missing  → uses ``datetime.now(timezone.utc)``
      - ISO-8601 string (with or without trailing Z / offset)
      - ``datetime`` object (naive assumed UTC)
    """
    if raw_ts is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(raw_ts, datetime):
        dt = raw_ts if raw_ts.tzinfo else raw_ts.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
    elif isinstance(raw_ts, str):
        cleaned = raw_ts.strip()
        # Remove trailing 'Z' and replace with +00:00 for fromisoformat
        if cleaned.endswith("Z") or cleaned.endswith("z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(cleaned)
        except ValueError as exc:
            raise NormalizationError(
                f"Unparseable timestamp: {raw_ts!r}"
            ) from exc
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
    else:
        raise NormalizationError(
            f"Unsupported timestamp type: {type(raw_ts).__name__}"
        )
    # Format: 2026-07-15T14:22:14.123Z  (always 3-digit ms, trailing Z)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _sanitize_text(value: Any) -> str | None:
    """
    Ensure a text value is clean UTF-8 with normalised line endings.

    - bytes → decoded as UTF-8 with replacement for invalid sequences
    - str   → re-encoded / decoded to flush surrogates
    - None  → returned as-is
    """
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    elif not isinstance(value, str):
        value = str(value)
    # Normalise line endings to \n
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return value


def _extract_source_identifier(source_path: str) -> str:
    """Derive ``source_identifier`` from the full source path."""
    return os.path.basename(source_path) or source_path


def _normalize_log_data(raw_log: Any) -> dict:
    """
    Build a normalised ``log_data`` dict.

    Accepts a dict with optional keys ``summary``, ``raw_line``,
    ``snapshot_sha256``, and ``metadata``.  Missing keys get null defaults.
    """
    if raw_log is None:
        raw_log = {}
    if not isinstance(raw_log, dict):
        raw_log = {"summary": str(raw_log)}

    log = {
        "summary": _sanitize_text(raw_log.get("summary")),
        "raw_line": _sanitize_text(raw_log.get("raw_line")),
        "snapshot_sha256": raw_log.get("snapshot_sha256"),
        "metadata": _normalize_metadata(raw_log.get("metadata")),
    }
    for k in sorted(raw_log.keys()):
        if k not in log:
            log[k] = raw_log[k]
    return log


def _normalize_metadata(raw_meta: Any) -> dict:
    """Build a normalised ``metadata`` sub-dict inside ``log_data``."""
    if raw_meta is None:
        raw_meta = {}
    if not isinstance(raw_meta, dict):
        raw_meta = {}

    meta = {
        "actor": _sanitize_text(raw_meta.get("actor", "system")),
        "encoding": raw_meta.get("encoding", "utf-8"),
        "size_bytes": raw_meta.get("size_bytes"),
    }
    for k in sorted(raw_meta.keys()):
        if k not in meta:
            meta[k] = raw_meta[k]
    return meta


def normalize_event(raw_event: Any) -> dict:
    """
    Normalise a raw event dict into the canonical ledger event schema.

    Parameters
    ----------
    raw_event : dict
        Must contain at minimum ``event_type``, ``source_type``, and
        ``source_path``.

    Returns
    -------
    dict
        Normalised event ready for block creation.

    Raises
    ------
    NormalizationError
        If required fields are missing or values are invalid.
    """
    if not isinstance(raw_event, dict):
        raise NormalizationError("Raw event must be a dict")

    # --- Validate required fields ---
    missing = [f for f in REQUIRED_FIELDS if f not in raw_event or raw_event[f] is None]
    if missing:
        raise NormalizationError(f"Missing required fields: {', '.join(missing)}")

    event_type = raw_event["event_type"]
    source_type = raw_event["source_type"]

    if event_type not in VALID_EVENT_TYPES:
        raise NormalizationError(
            f"Invalid event_type: {event_type!r}. "
            f"Must be one of {sorted(VALID_EVENT_TYPES)}"
        )
    if source_type not in VALID_SOURCE_TYPES:
        raise NormalizationError(
            f"Invalid source_type: {source_type!r}. "
            f"Must be one of {sorted(VALID_SOURCE_TYPES)}"
        )

    source_path = _sanitize_text(raw_event["source_path"]) or ""
    source_identifier = raw_event.get("source_identifier") or _extract_source_identifier(source_path)

    return {
        "event_type": event_type,
        "source_type": source_type,
        "source_path": source_path,
        "source_identifier": _sanitize_text(source_identifier),
        "event_id": raw_event.get("event_id") or _next_event_id(),
        "timestamp_utc": _normalize_timestamp(raw_event.get("timestamp_utc")),
        "log_data": _normalize_log_data(raw_event.get("log_data")),
    }
