"""Tests for the JSONL storage backend."""

import json
import pytest

from backend.core.storage import Storage, StorageError


@pytest.fixture
def storage(tmp_path):
    """Create a Storage instance with a temporary data directory."""
    s = Storage(tmp_path / "data")
    s.ensure_directories()
    return s


def _make_block(index: int = 0, current_hash: str = "a" * 64) -> dict:
    """Create a minimal block dict for testing."""
    return {
        "schema_version": "1.0",
        "block_index": index,
        "timestamp_utc": "2026-07-15T14:22:14.123Z",
        "event_type": "genesis" if index == 0 else "file_modified",
        "source_type": "system",
        "source_path": "system://genesis",
        "source_identifier": "genesis",
        "event_id": f"evt-{index:06d}",
        "log_data": {"summary": f"Block {index}", "raw_line": None,
                     "snapshot_sha256": None,
                     "metadata": {"actor": "system", "encoding": "utf-8",
                                  "size_bytes": None}},
        "previous_hash": "0" * 64,
        "current_hash": current_hash,
        "ingest_sequence": index,
        "verification_hint": {"segment_id": "segment-0001",
                              "expected_chain_state": "healthy"},
    }


# ── Directory creation ─────────────────────────────────────────────────

class TestEnsureDirectories:
    def test_creates_all_directories(self, storage):
        assert storage.ledger_dir.exists()
        assert storage.archive_dir.exists()
        assert storage.checkpoint_dir.exists()
        assert storage.watched_dir.exists()
        assert storage.runtime_dir.exists()

    def test_idempotent(self, storage):
        # Call again — should not raise
        storage.ensure_directories()


# ── Block append and read ──────────────────────────────────────────────

class TestAppendAndRead:
    def test_roundtrip_single_block(self, storage):
        block = _make_block(0)
        storage.append_block(block)
        blocks = storage.read_all_blocks()
        assert len(blocks) == 1
        assert blocks[0] == block

    def test_roundtrip_multiple_blocks(self, storage):
        for i in range(5):
            storage.append_block(_make_block(i, current_hash=f"{i:064d}"))
        blocks = storage.read_all_blocks()
        assert len(blocks) == 5
        assert [b["block_index"] for b in blocks] == [0, 1, 2, 3, 4]

    def test_append_creates_file(self, storage):
        assert not storage.ledger_file.exists()
        storage.append_block(_make_block(0))
        assert storage.ledger_file.exists()

    def test_jsonl_format(self, storage):
        storage.append_block(_make_block(0))
        storage.append_block(_make_block(1))
        lines = storage.ledger_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            json.loads(line)  # should not raise


# ── Read by index ──────────────────────────────────────────────────────

class TestReadByIndex:
    def test_finds_existing_block(self, storage):
        for i in range(3):
            storage.append_block(_make_block(i, current_hash=f"{i:064d}"))
        block = storage.read_block_by_index(1)
        assert block is not None
        assert block["block_index"] == 1

    def test_returns_none_for_missing(self, storage):
        storage.append_block(_make_block(0))
        assert storage.read_block_by_index(99) is None

    def test_empty_ledger_returns_none(self, storage):
        assert storage.read_block_by_index(0) is None


# ── Get last block ─────────────────────────────────────────────────────

class TestGetLastBlock:
    def test_returns_last(self, storage):
        for i in range(4):
            storage.append_block(_make_block(i, current_hash=f"{i:064d}"))
        last = storage.get_last_block()
        assert last["block_index"] == 3

    def test_single_block(self, storage):
        storage.append_block(_make_block(0))
        last = storage.get_last_block()
        assert last["block_index"] == 0

    def test_empty_returns_none(self, storage):
        assert storage.get_last_block() is None


# ── Block count ────────────────────────────────────────────────────────

class TestGetBlockCount:
    def test_empty(self, storage):
        assert storage.get_block_count() == 0

    def test_after_appends(self, storage):
        for i in range(7):
            storage.append_block(_make_block(i))
        assert storage.get_block_count() == 7


# ── Streaming ──────────────────────────────────────────────────────────

class TestStreamBlocks:
    def test_yields_all_blocks(self, storage):
        for i in range(3):
            storage.append_block(_make_block(i))
        streamed = list(storage.stream_blocks())
        assert len(streamed) == 3

    def test_empty_file_yields_nothing(self, storage):
        assert list(storage.stream_blocks()) == []


# ── State save/load ────────────────────────────────────────────────────

class TestState:
    def test_roundtrip(self, storage):
        state = {"chain_length": 5, "frozen": False, "last_hash": "x" * 64}
        storage.save_state(state)
        loaded = storage.load_state()
        assert loaded == state

    def test_load_missing_returns_none(self, storage):
        assert storage.load_state() is None

    def test_overwrite(self, storage):
        storage.save_state({"v": 1})
        storage.save_state({"v": 2})
        assert storage.load_state()["v"] == 2


# ── Alerts ─────────────────────────────────────────────────────────────

class TestAlerts:
    def test_append_and_read(self, storage):
        alert = {"type": "chain_break", "block_index": 5}
        storage.append_alert(alert)
        alerts = storage.read_alerts()
        assert len(alerts) == 1
        assert alerts[0] == alert

    def test_empty_returns_list(self, storage):
        assert storage.read_alerts() == []
