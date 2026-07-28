"""Tests for SourceWatcher capture daemon."""

import json
import time
from pathlib import Path

import pytest

from backend.capture.watcher import SourceWatcher
from backend.core.ledger_engine import LedgerEngine
from backend.core.state_manager import StateManager
from backend.core.storage import Storage


@pytest.fixture
def capture_setup(tmp_path: Path):
    """Fixture returning (storage, engine, state_manager, watched_dir)."""
    storage = Storage(tmp_path)
    storage.ensure_directories()
    engine = LedgerEngine(storage)
    engine.initialize()
    state_manager = StateManager(storage)
    state_manager.load_from_disk()
    watched_dir = tmp_path / "watched"
    return storage, engine, state_manager, watched_dir


def test_watcher_initial_snapshot(capture_setup):
    storage, engine, state_manager, watched_dir = capture_setup
    conf_file = watched_dir / "app.json"
    conf_file.write_text('{"setting": true}', encoding="utf-8")

    watcher = SourceWatcher(engine, storage, state_manager, watched_paths=[conf_file], interval_seconds=1.0)
    watcher.scan_once()

    assert engine.get_chain_length() == 2  # Genesis + initial snapshot
    last_block = engine.get_last_block()
    assert last_block["event_type"] == "config_changed"
    assert last_block["source_identifier"] == "app.json"
    assert last_block["log_data"]["snapshot_sha256"] is not None

    statuses = watcher.get_monitored_sources()
    assert len(statuses) == 1
    assert statuses[0]["status"] == "monitored"
    assert statuses[0]["size_bytes"] == len('{"setting": true}')


def test_watcher_detects_modification(capture_setup):
    storage, engine, state_manager, watched_dir = capture_setup
    log_file = watched_dir / "system.log"
    log_file.write_text("initial log line\n", encoding="utf-8")

    watcher = SourceWatcher(engine, storage, state_manager, watched_paths=[log_file], interval_seconds=1.0)
    watcher.scan_once()
    assert engine.get_chain_length() == 2

    # Modify file
    log_file.write_text("initial log line\nsecond line\n", encoding="utf-8")
    watcher.scan_once()

    assert engine.get_chain_length() == 3
    last_block = engine.get_last_block()
    assert last_block["event_type"] == "log_entry"
    assert last_block["log_data"]["summary"] == "Data added to file: system.log"
    assert last_block["log_data"]["metadata"]["previous_sha256"] is not None


def test_watcher_detects_missing_file(capture_setup):
    storage, engine, state_manager, watched_dir = capture_setup
    bin_file = watched_dir / "app.bin"
    bin_file.write_bytes(b"\x01\x02\x03")

    watcher = SourceWatcher(engine, storage, state_manager, watched_paths=[bin_file], interval_seconds=1.0)
    watcher.scan_once()
    assert engine.get_chain_length() == 2

    # Delete file
    bin_file.unlink()
    watcher.scan_once()

    assert engine.get_chain_length() == 3
    last_block = engine.get_last_block()
    assert last_block["event_type"] == "file_deleted"
    assert last_block["log_data"]["summary"] == "Monitored file app.bin was deleted or missing"

    statuses = watcher.get_monitored_sources()
    assert statuses[0]["status"] == "missing"


def test_watcher_respects_frozen_engine(capture_setup):
    storage, engine, state_manager, watched_dir = capture_setup
    txt_file = watched_dir / "notes.txt"
    txt_file.write_text("hello", encoding="utf-8")

    watcher = SourceWatcher(engine, storage, state_manager, watched_paths=[txt_file], interval_seconds=1.0)
    engine.freeze()
    state_manager.set_frozen(True)

    # Should not crash and should not append blocks when frozen
    watcher.scan_once()
    assert engine.get_chain_length() == 1
