"""
Ledger block schema and factory functions.

Defines the canonical block data structure matching the TRD §Single
Ledger Block Schema, and provides factory functions for creating
genesis and normal blocks.
"""

from typing import Any

from backend.core.hasher import canonical_serialize, compute_hash

# ── Constants ──────────────────────────────────────────────────────────
SCHEMA_VERSION = "1.0"
GENESIS_PREVIOUS_HASH = "0" * 64  # 64 hex zeros

# Fields that every block must contain
REQUIRED_BLOCK_FIELDS = (
    "schema_version",
    "block_index",
    "timestamp_utc",
    "event_type",
    "source_type",
    "source_path",
    "source_identifier",
    "event_id",
    "log_data",
    "previous_hash",
    "current_hash",
    "ingest_sequence",
    "verification_hint",
)


class BlockCreationError(Exception):
    """Raised when a block cannot be constructed."""


def _finalize_block(block: dict, previous_hash: str) -> dict:
    block["current_hash"] = compute_hash(previous_hash, canonical_serialize(block))
    return block


def create_genesis_block() -> dict:
    """Create block 0 — the genesis block."""
    from backend.core.normalizer import _normalize_timestamp
    return _finalize_block({
        "schema_version": SCHEMA_VERSION,
        "block_index": 0,
        "timestamp_utc": _normalize_timestamp(None),
        "event_type": "genesis",
        "source_type": "system",
        "source_path": "system://genesis",
        "source_identifier": "genesis",
        "event_id": "evt-000000",
        "log_data": {
            "summary": "Ledger genesis block created",
            "raw_line": None,
            "snapshot_sha256": None,
            "metadata": {"actor": "system", "encoding": "utf-8", "size_bytes": None},
        },
        "previous_hash": GENESIS_PREVIOUS_HASH,
        "current_hash": "",
        "ingest_sequence": 0,
        "verification_hint": {"segment_id": "segment-0001", "expected_chain_state": "healthy"},
    }, GENESIS_PREVIOUS_HASH)


def create_block(
    block_index: int,
    normalized_event: dict,
    previous_hash: str,
) -> dict:
    """
    Create a new ledger block from a normalised event.

    Parameters
    ----------
    block_index : int
        The sequential index for this block (must be > 0).
    normalized_event : dict
        Output of ``normalizer.normalize_event()``.
    previous_hash : str
        The ``current_hash`` of the immediately preceding block.

    Returns
    -------
    dict
        A complete block with ``current_hash`` computed.

    Raises
    ------
    BlockCreationError
        If the index is invalid or required event fields are missing.
    """
    if block_index < 1:
        raise BlockCreationError(
            f"block_index must be >= 1 for non-genesis blocks, got {block_index}"
        )
    if not previous_hash or len(previous_hash) != 64:
        raise BlockCreationError(
            f"previous_hash must be a 64-char hex string, got {previous_hash!r}"
        )

    return _finalize_block({
        "schema_version": SCHEMA_VERSION,
        "block_index": block_index,
        "timestamp_utc": normalized_event["timestamp_utc"],
        "event_type": normalized_event["event_type"],
        "source_type": normalized_event["source_type"],
        "source_path": normalized_event["source_path"],
        "source_identifier": normalized_event["source_identifier"],
        "event_id": normalized_event["event_id"],
        "log_data": normalized_event["log_data"],
        "previous_hash": previous_hash,
        "current_hash": "",  # placeholder — computed below
        "ingest_sequence": block_index,
        "verification_hint": {
            "segment_id": f"segment-{((block_index - 1) // 10_000) + 1:04d}",
            "expected_chain_state": "healthy",
        },
    }, previous_hash)


def validate_block_schema(block: Any) -> tuple[bool, list[str]]:
    """Validate that a block dict has all required fields with sane types."""
    if not isinstance(block, dict):
        return False, ["Block is not a dict"]
    missing = [f for f in REQUIRED_BLOCK_FIELDS if f not in block]
    if missing:
        return False, [f"Missing required field: {f}" for f in missing]
    errors: list[str] = []
    if block["schema_version"] != SCHEMA_VERSION:
        errors.append(f"Unsupported schema_version: {block['schema_version']!r}")
    if not isinstance(block["block_index"], int) or block["block_index"] < 0:
        errors.append(f"Invalid block_index: {block['block_index']!r}")
    for k in ("timestamp_utc", "previous_hash", "current_hash"):
        if not isinstance(block[k], str) or (k in ("previous_hash", "current_hash") and len(block[k]) != 64):
            errors.append(f"{k} must be a {'64-char hex ' if 'hash' in k else ''}string")
    if not isinstance(block["log_data"], dict):
        errors.append("log_data must be a dict")
    return not errors, errors
