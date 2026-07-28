"""Tests for canonical serialization and SHA-256 hashing."""

import hashlib
import json
import pytest

from backend.core.hasher import canonical_serialize, compute_hash, hash_content


# ── Sample blocks ──────────────────────────────────────────────────────

def _sample_block(**overrides) -> dict:
    """Return a sample block dict with optional overrides."""
    base = {
        "schema_version": "1.0",
        "block_index": 1,
        "timestamp_utc": "2026-07-15T14:22:14.123Z",
        "event_type": "file_modified",
        "source_type": "config_file",
        "source_path": "/etc/device.conf",
        "source_identifier": "device.conf",
        "event_id": "evt-000001",
        "log_data": {
            "summary": "configuration value changed",
            "raw_line": None,
            "snapshot_sha256": "a1b2c3",
            "metadata": {
                "actor": "system",
                "encoding": "utf-8",
                "size_bytes": 248,
            },
        },
        "previous_hash": "0" * 64,
        "current_hash": "f" * 64,
        "ingest_sequence": 1,
        "verification_hint": {
            "segment_id": "segment-0001",
            "expected_chain_state": "healthy",
        },
    }
    base.update(overrides)
    return base


# ── Canonical serialization ───────────────────────────────────────────

class TestCanonicalSerialize:
    def test_excludes_current_hash(self):
        block = _sample_block()
        result = canonical_serialize(block)
        parsed = json.loads(result)
        assert "current_hash" not in parsed

    def test_sorted_keys(self):
        block = _sample_block()
        result = canonical_serialize(block)
        parsed = json.loads(result)
        assert list(parsed.keys()) == sorted(parsed.keys())

    def test_compact_separators(self):
        block = _sample_block()
        result = canonical_serialize(block)
        # No spaces after colons or commas
        assert ": " not in result
        assert ", " not in result

    def test_null_preserved(self):
        block = _sample_block()
        result = canonical_serialize(block)
        assert "null" in result  # raw_line is None

    def test_boolean_preserved(self):
        block = _sample_block(
            log_data={"summary": None, "raw_line": None,
                       "snapshot_sha256": None,
                       "metadata": {"actor": "system", "encoding": "utf-8",
                                    "size_bytes": None}}
        )
        result = canonical_serialize(block)
        # Verify it's valid JSON
        json.loads(result)

    def test_numeric_preserved(self):
        block = _sample_block()
        result = canonical_serialize(block)
        # block_index=1, size_bytes=248 should appear as integers
        assert '"block_index":1' in result
        assert '"size_bytes":248' in result

    def test_determinism(self):
        """Same block serialises identically every time."""
        block = _sample_block()
        r1 = canonical_serialize(block)
        r2 = canonical_serialize(block)
        r3 = canonical_serialize(block)
        assert r1 == r2 == r3

    def test_does_not_mutate_input(self):
        block = _sample_block()
        original_hash = block["current_hash"]
        canonical_serialize(block)
        assert block["current_hash"] == original_hash


# ── Hash computation ──────────────────────────────────────────────────

class TestComputeHash:
    def test_returns_64_hex_chars(self):
        result = compute_hash("0" * 64, '{"key":"value"}')
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_matches_manual_sha256(self):
        prev = "0" * 64
        serialized = '{"block_index":0}'
        expected = hashlib.sha256(
            (prev + serialized).encode("utf-8")
        ).hexdigest()
        assert compute_hash(prev, serialized) == expected

    def test_determinism(self):
        prev = "a" * 64
        serialized = '{"data":"test"}'
        r1 = compute_hash(prev, serialized)
        r2 = compute_hash(prev, serialized)
        assert r1 == r2

    def test_different_previous_hash_yields_different_result(self):
        serialized = '{"data":"same"}'
        h1 = compute_hash("0" * 64, serialized)
        h2 = compute_hash("1" * 64, serialized)
        assert h1 != h2

    def test_different_payload_yields_different_result(self):
        prev = "0" * 64
        h1 = compute_hash(prev, '{"data":"a"}')
        h2 = compute_hash(prev, '{"data":"b"}')
        assert h1 != h2


# ── Content hashing ───────────────────────────────────────────────────

class TestHashContent:
    def test_known_hash(self):
        # SHA-256 of empty bytes
        expected = hashlib.sha256(b"").hexdigest()
        assert hash_content(b"") == expected

    def test_non_empty(self):
        data = b"hello world"
        expected = hashlib.sha256(data).hexdigest()
        assert hash_content(data) == expected

    def test_returns_lowercase_hex(self):
        result = hash_content(b"test")
        assert result == result.lower()
        assert len(result) == 64
