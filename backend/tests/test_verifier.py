"""
Tests for the chain verification engine.
"""

import json
import pytest
from pathlib import Path

from backend.core.block import (
    create_genesis_block,
    create_block,
    GENESIS_PREVIOUS_HASH,
)
from backend.core.hasher import canonical_serialize, compute_hash
from backend.core.normalizer import normalize_event, reset_event_counter
from backend.core.storage import Storage
from backend.core.verifier import (
    verify_chain,
    VerificationResult,
    VerificationFailure,
    FailureType,
    reset_verification_counter,
)


@pytest.fixture(autouse=True)
def _reset_counters():
    """Reset global counters before each test."""
    reset_event_counter(0)
    reset_verification_counter(0)


@pytest.fixture
def storage(tmp_path):
    """Create a Storage instance in a temp directory."""
    s = Storage(tmp_path)
    s.ensure_directories()
    return s


def _make_event(index: int, event_type: str = "file_modified") -> dict:
    """Helper to create a raw event dict."""
    return {
        "event_type": event_type,
        "source_type": "config_file",
        "source_path": f"/etc/test{index}.conf",
        "log_data": {"summary": f"Test event {index}"},
    }


def _build_chain(storage: Storage, count: int) -> list[dict]:
    """Build a valid chain of `count` blocks (including genesis)."""
    genesis = create_genesis_block()
    storage.append_block(genesis)
    blocks = [genesis]

    for i in range(1, count):
        normalized = normalize_event(_make_event(i))
        block = create_block(i, normalized, blocks[-1]["current_hash"])
        storage.append_block(block)
        blocks.append(block)

    return blocks


# ── Healthy chain tests ───────────────────────────────────────────────


class TestHealthyChain:
    """Verify that valid chains pass verification."""

    def test_empty_ledger_passes(self, storage):
        """Empty ledger (no blocks) is healthy."""
        result = verify_chain(storage)
        assert result.healthy is True
        assert result.blocks_checked == 0
        assert result.failures == []
        assert result.first_invalid_index is None

    def test_genesis_only_passes(self, storage):
        """Single genesis block passes."""
        genesis = create_genesis_block()
        storage.append_block(genesis)

        result = verify_chain(storage)
        assert result.healthy is True
        assert result.blocks_checked == 1

    def test_multi_block_chain_passes(self, storage):
        """Chain of 5 blocks passes."""
        _build_chain(storage, 5)

        result = verify_chain(storage)
        assert result.healthy is True
        assert result.blocks_checked == 5
        assert result.failures == []

    def test_large_chain_passes(self, storage):
        """Chain of 20 blocks passes."""
        _build_chain(storage, 20)

        result = verify_chain(storage)
        assert result.healthy is True
        assert result.blocks_checked == 20


class TestVerificationResult:
    """Verify the structure of VerificationResult."""

    def test_result_has_verification_id(self, storage):
        result = verify_chain(storage)
        assert result.verification_id.startswith("ver-")

    def test_result_has_timestamp(self, storage):
        result = verify_chain(storage)
        assert result.timestamp_utc.endswith("Z")

    def test_result_has_duration(self, storage):
        result = verify_chain(storage)
        assert isinstance(result.duration_ms, float)
        assert result.duration_ms >= 0

    def test_result_to_dict(self, storage):
        _build_chain(storage, 3)
        result = verify_chain(storage)
        d = result.to_dict()
        assert d["healthy"] is True
        assert d["blocks_checked"] == 3
        assert isinstance(d["failures"], list)

    def test_verification_ids_are_sequential(self, storage):
        r1 = verify_chain(storage)
        r2 = verify_chain(storage)
        # IDs should increment
        id1 = int(r1.verification_id.split("-")[1])
        id2 = int(r2.verification_id.split("-")[1])
        assert id2 > id1


# ── Hash tampering detection ─────────────────────────────────────────


class TestHashMismatch:
    """Verify detection of tampered current_hash."""

    def test_tampered_current_hash(self, storage):
        """Modifying current_hash triggers HASH_MISMATCH."""
        blocks = _build_chain(storage, 3)

        # Tamper block 1's current_hash directly in the file
        self._tamper_block_field(storage, 1, "current_hash", "f" * 64)

        result = verify_chain(storage)
        assert result.healthy is False
        assert result.first_invalid_index == 1

        types = [f.failure_type for f in result.failures]
        assert FailureType.HASH_MISMATCH in types

    def test_tampered_log_data(self, storage):
        """Modifying block content changes recomputed hash → HASH_MISMATCH."""
        _build_chain(storage, 3)

        self._tamper_block_field(
            storage, 1, "log_data",
            {"summary": "TAMPERED", "raw_line": None,
             "snapshot_sha256": None,
             "metadata": {"actor": "system", "encoding": "utf-8",
                          "size_bytes": None}},
        )

        result = verify_chain(storage)
        assert result.healthy is False

        types = [f.failure_type for f in result.failures]
        assert FailureType.HASH_MISMATCH in types

    @staticmethod
    def _tamper_block_field(storage: Storage, index: int, field: str, value):
        """Rewrite the ledger file with one field changed on a specific block."""
        blocks = storage.read_all_blocks()
        blocks[index][field] = value
        # Rewrite entire file
        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            for b in blocks:
                line = json.dumps(b, sort_keys=True, separators=(",", ":"))
                fh.write(line + "\n")


# ── Previous hash mismatch ───────────────────────────────────────────


class TestPreviousHashMismatch:
    """Verify detection of tampered previous_hash."""

    def test_tampered_previous_hash(self, storage):
        """Wrong previous_hash triggers PREVIOUS_HASH_MISMATCH."""
        _build_chain(storage, 3)

        blocks = storage.read_all_blocks()
        blocks[2]["previous_hash"] = "a" * 64
        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            for b in blocks:
                fh.write(json.dumps(b, sort_keys=True, separators=(",", ":")) + "\n")

        result = verify_chain(storage)
        assert result.healthy is False

        types = [f.failure_type for f in result.failures]
        assert FailureType.PREVIOUS_HASH_MISMATCH in types

    def test_genesis_wrong_previous_hash(self, storage):
        """Genesis with non-zero previous_hash triggers failure."""
        genesis = create_genesis_block()
        genesis["previous_hash"] = "b" * 64
        # Need to recompute hash for the modified previous_hash
        # but we deliberately leave it wrong to detect the break

        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(genesis, sort_keys=True, separators=(",", ":")) + "\n")

        result = verify_chain(storage)
        assert result.healthy is False


# ── Index problems ───────────────────────────────────────────────────


class TestIndexProblems:
    """Verify detection of index gaps and duplicates."""

    def test_index_gap(self, storage):
        """Skipping a block_index triggers INDEX_GAP."""
        blocks = _build_chain(storage, 4)

        # Remove block 2 to create a gap (0, 1, 3)
        remaining = [blocks[0], blocks[1], blocks[3]]
        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            for b in remaining:
                fh.write(json.dumps(b, sort_keys=True, separators=(",", ":")) + "\n")

        result = verify_chain(storage)
        assert result.healthy is False

        types = [f.failure_type for f in result.failures]
        assert FailureType.INDEX_GAP in types

    def test_index_duplicate(self, storage):
        """Duplicate block_index triggers INDEX_DUPLICATE."""
        blocks = _build_chain(storage, 3)

        # Duplicate block 1
        duped = [blocks[0], blocks[1], blocks[1]]
        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            for b in duped:
                fh.write(json.dumps(b, sort_keys=True, separators=(",", ":")) + "\n")

        result = verify_chain(storage)
        assert result.healthy is False

        types = [f.failure_type for f in result.failures]
        assert FailureType.INDEX_DUPLICATE in types

    def test_first_block_not_zero(self, storage):
        """Chain starting at index 1 instead of 0 triggers failure."""
        blocks = _build_chain(storage, 3)
        remaining = blocks[1:]  # skip genesis
        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            for b in remaining:
                fh.write(json.dumps(b, sort_keys=True, separators=(",", ":")) + "\n")

        result = verify_chain(storage)
        assert result.healthy is False


# ── Truncation ───────────────────────────────────────────────────────


class TestTruncation:
    """Verify detection of unexpected truncation."""

    def test_truncation_detected(self, storage):
        """Fewer blocks than expected triggers TRUNCATION."""
        _build_chain(storage, 3)

        result = verify_chain(storage, expected_count=5)
        assert result.healthy is False

        types = [f.failure_type for f in result.failures]
        assert FailureType.TRUNCATION in types

    def test_exact_count_passes(self, storage):
        """Correct expected_count does not trigger truncation."""
        _build_chain(storage, 5)

        result = verify_chain(storage, expected_count=5)
        assert result.healthy is True

    def test_more_blocks_than_expected(self, storage):
        """More blocks than expected also triggers TRUNCATION."""
        _build_chain(storage, 5)

        result = verify_chain(storage, expected_count=3)
        assert result.healthy is False

        types = [f.failure_type for f in result.failures]
        assert FailureType.TRUNCATION in types


# ── Schema violation ─────────────────────────────────────────────────


class TestSchemaViolation:
    """Verify detection of schema-invalid blocks."""

    def test_missing_field(self, storage):
        """Block with missing required field triggers SCHEMA_INVALID."""
        genesis = create_genesis_block()
        del genesis["event_type"]  # remove required field

        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(genesis, sort_keys=True, separators=(",", ":")) + "\n")

        result = verify_chain(storage)
        assert result.healthy is False

        types = [f.failure_type for f in result.failures]
        assert FailureType.SCHEMA_INVALID in types


# ── Failure details ──────────────────────────────────────────────────


class TestFailureDetails:
    """Verify that failure objects carry useful details."""

    def test_hash_mismatch_has_stored_and_recomputed(self, storage):
        _build_chain(storage, 3)

        blocks = storage.read_all_blocks()
        blocks[1]["current_hash"] = "f" * 64
        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            for b in blocks:
                fh.write(json.dumps(b, sort_keys=True, separators=(",", ":")) + "\n")

        result = verify_chain(storage)
        hm = [f for f in result.failures if f.failure_type == FailureType.HASH_MISMATCH]
        assert len(hm) >= 1
        assert "stored" in hm[0].details
        assert "recomputed" in hm[0].details

    def test_failure_to_dict(self, storage):
        f = VerificationFailure(
            failure_type=FailureType.HASH_MISMATCH,
            block_index=5,
            message="test",
            details={"key": "val"},
        )
        d = f.to_dict()
        assert d["failure_type"] == "hash_mismatch"
        assert d["block_index"] == 5

    def test_first_invalid_index_is_earliest(self, storage):
        """first_invalid_index points to the earliest failure."""
        blocks = _build_chain(storage, 5)

        # Tamper blocks 2 and 3
        blocks[2]["current_hash"] = "a" * 64
        blocks[3]["current_hash"] = "b" * 64
        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            for b in blocks:
                fh.write(json.dumps(b, sort_keys=True, separators=(",", ":")) + "\n")

        result = verify_chain(storage)
        assert result.first_invalid_index == 2
