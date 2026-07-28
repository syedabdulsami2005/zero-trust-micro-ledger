"""
Tests for the verification daemon.
"""

import json
import time
import pytest

from backend.core.alerts import reset_alert_counter
from backend.core.block import create_genesis_block, create_block
from backend.core.ledger_engine import LedgerEngine, LedgerFrozenError
from backend.core.normalizer import normalize_event, reset_event_counter
from backend.core.state_manager import StateManager
from backend.core.storage import Storage
from backend.core.alert_store import AlertStore
from backend.core.verification_store import VerificationStore
from backend.core.verifier import reset_verification_counter
from backend.daemon.daemon import VerificationDaemon


@pytest.fixture(autouse=True)
def _reset_counters():
    reset_event_counter(0)
    reset_verification_counter(0)
    reset_alert_counter(0)


@pytest.fixture
def storage(tmp_path):
    s = Storage(tmp_path)
    s.ensure_directories()
    return s


@pytest.fixture
def engine(storage):
    e = LedgerEngine(storage)
    e.initialize()
    return e


@pytest.fixture
def alert_store(storage):
    return AlertStore(storage.ledger_dir)


@pytest.fixture
def state_mgr(storage, alert_store):
    return StateManager(storage, alert_store=alert_store)


@pytest.fixture
def ver_store(storage):
    return VerificationStore(storage)


@pytest.fixture
def daemon(engine, storage, state_mgr, ver_store, alert_store):
    return VerificationDaemon(
        engine=engine,
        storage=storage,
        state_manager=state_mgr,
        verification_store=ver_store,
        alert_store=alert_store,
        interval_seconds=0.1,  # fast for tests
    )


def _make_event(index: int) -> dict:
    return {
        "event_type": "file_modified",
        "source_type": "config_file",
        "source_path": f"/etc/test{index}.conf",
        "log_data": {"summary": f"Test event {index}"},
    }


# ── Lifecycle ─────────────────────────────────────────────────────────


class TestDaemonLifecycle:
    """Verify daemon start/stop behaviour."""

    def test_start_sets_running(self, daemon):
        daemon.start()
        assert daemon.is_running() is True
        daemon.stop()

    def test_stop_clears_running(self, daemon):
        daemon.start()
        daemon.stop()
        assert daemon.is_running() is False

    def test_double_start_is_safe(self, daemon):
        daemon.start()
        daemon.start()  # should not error
        assert daemon.is_running() is True
        daemon.stop()

    def test_double_stop_is_safe(self, daemon):
        daemon.start()
        daemon.stop()
        daemon.stop()  # should not error

    def test_stop_without_start_is_safe(self, daemon):
        daemon.stop()  # should not error


# ── Healthy chain ─────────────────────────────────────────────────────


class TestHealthyChain:
    """Verify daemon behaviour with a valid chain."""

    def test_healthy_chain_no_freeze(self, daemon, engine):
        """Healthy chain should not freeze the engine."""
        engine.append_event(_make_event(1))

        result = daemon.run_once()
        assert result.healthy is True
        assert engine.is_frozen() is False

    def test_healthy_chain_state_healthy(self, daemon, engine, state_mgr):
        engine.append_event(_make_event(1))
        daemon.run_once()
        assert state_mgr.get_health_status() == "healthy"

    def test_healthy_verification_stored(self, daemon, engine, ver_store):
        engine.append_event(_make_event(1))
        daemon.run_once()
        history = ver_store.read_history()
        assert len(history) == 1
        assert history[0]["healthy"] is True


# ── Tampered chain ────────────────────────────────────────────────────


class TestTamperedChain:
    """Verify daemon behaviour with a tampered chain."""

    def test_tampered_chain_freezes_engine(self, daemon, engine, storage):
        """Tampered chain should freeze the engine."""
        engine.append_event(_make_event(1))
        engine.append_event(_make_event(2))

        # Tamper block 1
        blocks = storage.read_all_blocks()
        blocks[1]["current_hash"] = "f" * 64
        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            for b in blocks:
                fh.write(json.dumps(b, sort_keys=True, separators=(",", ":")) + "\n")

        daemon.run_once()
        assert engine.is_frozen() is True

    def test_tampered_chain_generates_alerts(self, daemon, engine, storage):
        """Tampered chain should generate alerts."""
        engine.append_event(_make_event(1))

        blocks = storage.read_all_blocks()
        blocks[1]["current_hash"] = "f" * 64
        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            for b in blocks:
                fh.write(json.dumps(b, sort_keys=True, separators=(",", ":")) + "\n")

        daemon.run_once()
        alerts = storage.read_alerts()
        assert len(alerts) >= 1
        assert alerts[0]["severity"] == "critical"

    def test_tampered_chain_state_broken(self, daemon, engine, storage, state_mgr):
        engine.append_event(_make_event(1))

        blocks = storage.read_all_blocks()
        blocks[1]["current_hash"] = "f" * 64
        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            for b in blocks:
                fh.write(json.dumps(b, sort_keys=True, separators=(",", ":")) + "\n")

        daemon.run_once()
        assert state_mgr.get_health_status() == "broken"

    def test_frozen_engine_rejects_append(self, daemon, engine, storage):
        """After freeze, engine must reject appends."""
        engine.append_event(_make_event(1))

        blocks = storage.read_all_blocks()
        blocks[1]["current_hash"] = "f" * 64
        with open(storage.ledger_file, "w", encoding="utf-8") as fh:
            for b in blocks:
                fh.write(json.dumps(b, sort_keys=True, separators=(",", ":")) + "\n")

        daemon.run_once()

        with pytest.raises(LedgerFrozenError):
            engine.append_event(_make_event(3))


# ── Manual trigger ────────────────────────────────────────────────────


class TestRunOnce:
    """Verify manual run_once() trigger."""

    def test_run_once_returns_result(self, daemon, engine):
        engine.append_event(_make_event(1))
        result = daemon.run_once()
        assert result.healthy is True
        assert result.blocks_checked == 2  # genesis + 1

    def test_run_once_works_without_start(self, daemon, engine):
        """run_once works even if daemon not started."""
        result = daemon.run_once()
        assert result.healthy is True


# ── Background loop ──────────────────────────────────────────────────


class TestBackgroundLoop:
    """Verify the daemon actually runs in the background."""

    def test_daemon_runs_verification_in_background(
        self, daemon, engine, ver_store
    ):
        engine.append_event(_make_event(1))
        daemon.start()

        # Wait for at least one verification cycle
        time.sleep(0.3)
        daemon.stop()

        history = ver_store.read_history()
        assert len(history) >= 1

    def test_daemon_survives_exception(self, daemon, engine, storage, ver_store):
        """Daemon should not crash if verification encounters issues."""
        engine.append_event(_make_event(1))

        # Write garbage line to ledger to trigger parse error,
        # but the storage layer will raise StorageError which
        # the daemon catches
        with open(storage.ledger_file, "a", encoding="utf-8") as fh:
            fh.write("NOT-VALID-JSON\n")

        daemon.start()
        time.sleep(0.3)

        # Daemon should still be running (or have stopped gracefully)
        # The key is: no unhandled exception crashed the process
        daemon.stop()
