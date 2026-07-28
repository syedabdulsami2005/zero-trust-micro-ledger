"""
Chain integrity verification engine.

Replays the entire ledger and validates every block against the 7 TRD
verification rules:
  1. Valid JSON (handled by storage layer)
  2. Required fields present
  3. Monotonic and contiguous block_index
  4. previous_hash matches prior block's current_hash
  5. Recomputed hash equals stored current_hash
  6. No unexpected truncation
  7. Segment metadata internally consistent
"""

import time
import itertools
from dataclasses import dataclass, field
from enum import Enum

from backend.core.block import validate_block_schema, GENESIS_PREVIOUS_HASH
from backend.core.hasher import canonical_serialize, compute_hash
from backend.core.normalizer import _normalize_timestamp
from backend.core.storage import Storage


class FailureType(Enum):
    """Classification of verification failures."""
    SCHEMA_INVALID = "schema_invalid"
    INDEX_GAP = "index_gap"
    INDEX_DUPLICATE = "index_duplicate"
    HASH_MISMATCH = "hash_mismatch"
    PREVIOUS_HASH_MISMATCH = "previous_hash_mismatch"
    TRUNCATION = "truncation"
    SEGMENT_INCONSISTENCY = "segment_inconsistency"


@dataclass
class VerificationFailure:
    """A single verification failure."""
    failure_type: FailureType
    block_index: int | None
    message: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON storage."""
        return {**vars(self), "failure_type": self.failure_type.value}


# Thread-safe monotonic verification ID counter
_ver_counter = itertools.count(1)


def _next_verification_id() -> str:
    """Generate a monotonically increasing verification ID."""
    return f"ver-{next(_ver_counter):06d}"


def reset_verification_counter(value: int = 0) -> None:
    """Reset the verification counter.  Intended for testing only."""
    global _ver_counter
    _ver_counter = itertools.count(value + 1)


@dataclass
class VerificationResult:
    """Outcome of a full chain verification pass."""
    verification_id: str
    healthy: bool
    blocks_checked: int
    first_invalid_index: int | None
    failures: list[VerificationFailure]
    timestamp_utc: str
    duration_ms: float

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON storage."""
        return {
            "verification_id": self.verification_id,
            "healthy": self.healthy,
            "blocks_checked": self.blocks_checked,
            "first_invalid_index": self.first_invalid_index,
            "failures": [f.to_dict() for f in self.failures],
            "timestamp_utc": self.timestamp_utc,
            "duration_ms": self.duration_ms,
        }


def verify_chain(
    storage: Storage,
    expected_count: int | None = None,
) -> VerificationResult:
    """
    Replay the full chain and validate every block.

    Parameters
    ----------
    storage : Storage
        Storage backend to stream blocks from.
    expected_count : int | None
        If provided, the chain must contain exactly this many blocks.
        A mismatch produces a ``TRUNCATION`` failure.

    Returns
    -------
    VerificationResult
        Full result with health status, failures, and timing.
    """
    start_time = time.monotonic()
    failures: list[VerificationFailure] = []
    first_invalid: int | None = None
    blocks_checked = 0
    prev_block: dict | None = None

    def _record_failure(
        ftype: FailureType,
        index: int | None,
        msg: str,
        details: dict | None = None,
    ) -> None:
        nonlocal first_invalid
        failures.append(VerificationFailure(ftype, index, msg, details or {}))
        if first_invalid is None and index is not None:
            first_invalid = index

    for block in storage.stream_blocks():
        idx = block.get("block_index")

        # Rule 2: Required fields present
        valid, schema_errors = validate_block_schema(block)
        if not valid or not isinstance(idx, int):
            _record_failure(
                FailureType.SCHEMA_INVALID,
                idx if isinstance(idx, int) else None,
                f"Schema validation failed at block {idx}",
                {"errors": schema_errors if not valid else ["block_index is not an int"]},
            )
            blocks_checked += 1
            prev_block = block
            continue

        # Rule 3: Monotonic and contiguous block_index
        if prev_block is not None and isinstance(prev_block.get("block_index"), int):
            prev_idx: int = prev_block["block_index"]
            expected_idx = prev_idx + 1
            if idx == prev_idx:
                _record_failure(
                    FailureType.INDEX_DUPLICATE,
                    idx,
                    f"Duplicate block_index {idx}",
                )
            elif idx != expected_idx:
                _record_failure(
                    FailureType.INDEX_GAP,
                    idx,
                    f"Expected block_index {expected_idx}, got {idx}",
                    {"expected": expected_idx, "actual": idx},
                )
        elif idx != 0:
            # First block must be genesis (index 0)
            _record_failure(
                FailureType.INDEX_GAP,
                idx,
                f"First block must have index 0, got {idx}",
            )

        # Rule 4: previous_hash matches prior block's current_hash
        if prev_block is not None:
            expected_prev = prev_block["current_hash"]
            if block["previous_hash"] != expected_prev:
                _record_failure(
                    FailureType.PREVIOUS_HASH_MISMATCH,
                    idx,
                    f"previous_hash mismatch at block {idx}",
                    {
                        "expected": expected_prev,
                        "actual": block["previous_hash"],
                    },
                )
        else:
            # Genesis block must reference null hash
            if block["previous_hash"] != GENESIS_PREVIOUS_HASH:
                _record_failure(
                    FailureType.PREVIOUS_HASH_MISMATCH,
                    idx,
                    "Genesis block previous_hash must be 64 zeros",
                    {"actual": block["previous_hash"]},
                )

        # Rule 5: Recomputed hash == stored current_hash
        serialized = canonical_serialize(block)
        recomputed = compute_hash(block["previous_hash"], serialized)
        if recomputed != block["current_hash"]:
            _record_failure(
                FailureType.HASH_MISMATCH,
                idx,
                f"Hash mismatch at block {idx}",
                {
                    "stored": block["current_hash"],
                    "recomputed": recomputed,
                },
            )

        # Rule 7: Segment metadata internally consistent
        hint = block.get("verification_hint", {})
        if hint:
            expected_segment = f"segment-{((max(idx - 1, 0)) // 10_000) + 1:04d}" if idx > 0 else "segment-0001"
            actual_segment = hint.get("segment_id")
            if actual_segment and actual_segment != expected_segment:
                _record_failure(
                    FailureType.SEGMENT_INCONSISTENCY,
                    idx,
                    f"Segment ID mismatch at block {idx}",
                    {
                        "expected": expected_segment,
                        "actual": actual_segment,
                    },
                )

        blocks_checked += 1
        prev_block = block

    # Rule 6: No unexpected truncation
    if expected_count is not None and blocks_checked != expected_count:
        _record_failure(
            FailureType.TRUNCATION,
            None,
            f"Expected {expected_count} blocks, found {blocks_checked}",
            {"expected": expected_count, "actual": blocks_checked},
        )

    elapsed_ms = (time.monotonic() - start_time) * 1000.0

    return VerificationResult(
        verification_id=_next_verification_id(),
        healthy=len(failures) == 0,
        blocks_checked=blocks_checked,
        first_invalid_index=first_invalid,
        failures=failures,
        timestamp_utc=_normalize_timestamp(None),
        duration_ms=round(elapsed_ms, 3),
    )
