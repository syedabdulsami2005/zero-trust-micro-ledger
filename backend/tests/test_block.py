"""Tests for the block schema and factory functions."""

import pytest

from backend.core.block import (
    GENESIS_PREVIOUS_HASH,
    SCHEMA_VERSION,
    BlockCreationError,
    create_block,
    create_genesis_block,
    validate_block_schema,
)
from backend.core.hasher import canonical_serialize, compute_hash


# ── Genesis block ──────────────────────────────────────────────────────

class TestGenesisBlock:
    def test_block_index_is_zero(self):
        genesis = create_genesis_block()
        assert genesis["block_index"] == 0

    def test_previous_hash_is_64_zeros(self):
        genesis = create_genesis_block()
        assert genesis["previous_hash"] == "0" * 64

    def test_event_type_is_genesis(self):
        genesis = create_genesis_block()
        assert genesis["event_type"] == "genesis"

    def test_source_type_is_system(self):
        genesis = create_genesis_block()
        assert genesis["source_type"] == "system"

    def test_schema_version(self):
        genesis = create_genesis_block()
        assert genesis["schema_version"] == SCHEMA_VERSION

    def test_current_hash_is_valid(self):
        genesis = create_genesis_block()
        h = genesis["current_hash"]
        assert isinstance(h, str)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_current_hash_is_correctly_computed(self):
        genesis = create_genesis_block()
        serialized = canonical_serialize(genesis)
        expected = compute_hash(GENESIS_PREVIOUS_HASH, serialized)
        assert genesis["current_hash"] == expected

    def test_passes_schema_validation(self):
        genesis = create_genesis_block()
        is_valid, errors = validate_block_schema(genesis)
        assert is_valid, errors


# ── Normal block creation ─────────────────────────────────────────────

def _sample_normalized_event() -> dict:
    return {
        "event_type": "file_modified",
        "source_type": "config_file",
        "source_path": "/etc/device.conf",
        "source_identifier": "device.conf",
        "event_id": "evt-000001",
        "timestamp_utc": "2026-07-15T14:22:14.123Z",
        "log_data": {
            "summary": "config changed",
            "raw_line": None,
            "snapshot_sha256": "abcdef1234567890" * 4,
            "metadata": {
                "actor": "system",
                "encoding": "utf-8",
                "size_bytes": 256,
            },
        },
    }


class TestCreateBlock:
    def test_block_index_set_correctly(self):
        block = create_block(1, _sample_normalized_event(), "a" * 64)
        assert block["block_index"] == 1

    def test_previous_hash_preserved(self):
        prev = "b" * 64
        block = create_block(1, _sample_normalized_event(), prev)
        assert block["previous_hash"] == prev

    def test_current_hash_computed(self):
        block = create_block(1, _sample_normalized_event(), "c" * 64)
        serialized = canonical_serialize(block)
        expected = compute_hash("c" * 64, serialized)
        assert block["current_hash"] == expected

    def test_event_fields_propagated(self):
        event = _sample_normalized_event()
        block = create_block(1, event, "d" * 64)
        assert block["event_type"] == event["event_type"]
        assert block["source_path"] == event["source_path"]
        assert block["event_id"] == event["event_id"]
        assert block["log_data"] == event["log_data"]

    def test_schema_version(self):
        block = create_block(1, _sample_normalized_event(), "e" * 64)
        assert block["schema_version"] == SCHEMA_VERSION

    def test_zero_index_raises(self):
        with pytest.raises(BlockCreationError, match="must be >= 1"):
            create_block(0, _sample_normalized_event(), "f" * 64)

    def test_invalid_previous_hash_raises(self):
        with pytest.raises(BlockCreationError, match="64-char hex"):
            create_block(1, _sample_normalized_event(), "short")

    def test_passes_schema_validation(self):
        block = create_block(1, _sample_normalized_event(), "a" * 64)
        is_valid, errors = validate_block_schema(block)
        assert is_valid, errors


# ── Schema validation ─────────────────────────────────────────────────

class TestValidateBlockSchema:
    def test_valid_block(self):
        block = create_genesis_block()
        is_valid, errors = validate_block_schema(block)
        assert is_valid
        assert errors == []

    def test_missing_field(self):
        block = create_genesis_block()
        del block["event_type"]
        is_valid, errors = validate_block_schema(block)
        assert not is_valid
        assert any("event_type" in e for e in errors)

    def test_non_dict_rejected(self):
        is_valid, errors = validate_block_schema("not a dict")
        assert not is_valid

    def test_bad_schema_version(self):
        block = create_genesis_block()
        block["schema_version"] = "99.0"
        is_valid, errors = validate_block_schema(block)
        assert not is_valid
        assert any("schema_version" in e for e in errors)

    def test_negative_block_index(self):
        block = create_genesis_block()
        block["block_index"] = -1
        is_valid, errors = validate_block_schema(block)
        assert not is_valid

    def test_short_hash_rejected(self):
        block = create_genesis_block()
        block["current_hash"] = "abc"
        is_valid, errors = validate_block_schema(block)
        assert not is_valid
