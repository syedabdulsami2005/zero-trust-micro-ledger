"""
Tests for the runtime state manager.
"""

import pytest

from backend.core.normalizer import reset_event_counter
from backend.core.state_manager import StateManager
from backend.core.storage import Storage
from backend.core.verifier import (
    FailureType,
    VerificationFailure,
    VerificationResult,
    reset_verification_counter,
)


@pytest.fixture(autouse=True)
def _reset_counters():
    reset_event_counter(0)
    reset_verification_counter(0)


@pytest.fixture
def storage(tmp_path):
    s = Storage(tmp_path)
    s.ensure_directories()
    return s


@pytest.fixture
def state_mgr(storage):
    return StateManager(storage)


def _make_result(
    healthy: bool = True,
    failures: list[VerificationFailure] | None = None,
) -> VerificationResult:
    if failures is None:
        failures = []
    return VerificationResult(
        verification_id="ver-000001",
        healthy=healthy,
        blocks_checked=5,
        first_invalid_index=failures[0].block_index if failures else None,
        failures=failures,
        timestamp_utc="2026-07-16T12:00:00.000Z",
        duration_ms=1.5,
    )


# ── Initial state ────────────────────────────────────────────────────


class TestInitialState:
    """State manager starts in a known healthy state."""

    def test_initial_health_is_healthy(self, state_mgr):
        assert state_mgr.get_health_status() == "healthy"

    def test_initial_state_dict(self, state_mgr):
        state = state_mgr.get_state()
        assert state["health_status"] == "healthy"
        assert state["frozen"] is False
        assert state["active_alert_count"] == 0
        assert state["total_verifications"] == 0
        assert state["last_verification_utc"] is None

    def test_initial_history_is_empty(self, state_mgr):
        assert state_mgr.get_history() == []


# ── Health transitions ───────────────────────────────────────────────


class TestHealthTransitions:
    """Verify state transitions: healthy → broken → healthy."""

    def test_healthy_after_clean_verification(self, state_mgr):
        result = _make_result(healthy=True)
        state_mgr.update_verification(result)
        assert state_mgr.get_health_status() == "healthy"

    def test_broken_after_hash_mismatch(self, state_mgr):
        failure = VerificationFailure(
            FailureType.HASH_MISMATCH, 1, "hash mismatch"
        )
        result = _make_result(healthy=False, failures=[failure])
        state_mgr.update_verification(result)
        assert state_mgr.get_health_status() == "broken"

    def test_broken_after_previous_hash_mismatch(self, state_mgr):
        failure = VerificationFailure(
            FailureType.PREVIOUS_HASH_MISMATCH, 2, "prev hash mismatch"
        )
        result = _make_result(healthy=False, failures=[failure])
        state_mgr.update_verification(result)
        assert state_mgr.get_health_status() == "broken"

    def test_degraded_after_index_gap(self, state_mgr):
        failure = VerificationFailure(
            FailureType.INDEX_GAP, 3, "index gap"
        )
        result = _make_result(healthy=False, failures=[failure])
        state_mgr.update_verification(result)
        assert state_mgr.get_health_status() == "degraded"

    def test_degraded_after_truncation(self, state_mgr):
        failure = VerificationFailure(
            FailureType.TRUNCATION, None, "truncation"
        )
        result = _make_result(healthy=False, failures=[failure])
        state_mgr.update_verification(result)
        assert state_mgr.get_health_status() == "degraded"

    def test_degraded_after_schema_invalid(self, state_mgr):
        failure = VerificationFailure(
            FailureType.SCHEMA_INVALID, 1, "schema invalid"
        )
        result = _make_result(healthy=False, failures=[failure])
        state_mgr.update_verification(result)
        assert state_mgr.get_health_status() == "degraded"

    def test_recovery_broken_to_healthy(self, state_mgr):
        """After a broken state, a clean verification restores healthy."""
        failure = VerificationFailure(
            FailureType.HASH_MISMATCH, 1, "mismatch"
        )
        bad_result = _make_result(healthy=False, failures=[failure])
        state_mgr.update_verification(bad_result)
        assert state_mgr.get_health_status() == "broken"

        good_result = _make_result(healthy=True)
        state_mgr.update_verification(good_result)
        assert state_mgr.get_health_status() == "healthy"

    def test_breaking_overrides_degrading(self, state_mgr):
        """If both breaking and degrading failures present, status is broken."""
        failures = [
            VerificationFailure(FailureType.INDEX_GAP, 1, "gap"),
            VerificationFailure(FailureType.HASH_MISMATCH, 2, "mismatch"),
        ]
        result = _make_result(healthy=False, failures=failures)
        state_mgr.update_verification(result)
        assert state_mgr.get_health_status() == "broken"


# ── Verification tracking ────────────────────────────────────────────


class TestVerificationTracking:
    """Verify counters and history are updated correctly."""

    def test_total_verifications_increments(self, state_mgr):
        r1 = _make_result()
        r2 = _make_result()
        state_mgr.update_verification(r1)
        state_mgr.update_verification(r2)
        assert state_mgr.get_state()["total_verifications"] == 2

    def test_last_verification_utc_updated(self, state_mgr):
        result = _make_result()
        state_mgr.update_verification(result)
        assert state_mgr.get_state()["last_verification_utc"] == result.timestamp_utc

    def test_history_records_results(self, state_mgr):
        r1 = _make_result()
        state_mgr.update_verification(r1)
        history = state_mgr.get_history()
        assert len(history) == 1
        assert history[0]["verification_id"] == "ver-000001"

    def test_history_is_newest_first(self, state_mgr):
        r1 = VerificationResult("ver-000001", True, 5, None, [],
                                "2026-07-16T12:00:00.000Z", 1.0)
        r2 = VerificationResult("ver-000002", True, 5, None, [],
                                "2026-07-16T12:01:00.000Z", 1.0)
        state_mgr.update_verification(r1)
        state_mgr.update_verification(r2)
        history = state_mgr.get_history()
        assert history[0]["verification_id"] == "ver-000002"


# ── Freeze state ─────────────────────────────────────────────────────



class TestFreezeState:
    """Verify freeze state tracking."""

    def test_set_frozen(self, state_mgr):
        state_mgr.set_frozen(True)
        assert state_mgr.get_state()["frozen"] is True

    def test_unfreeze(self, state_mgr):
        state_mgr.set_frozen(True)
        state_mgr.set_frozen(False)
        assert state_mgr.get_state()["frozen"] is False


# ── Persistence ──────────────────────────────────────────────────────


class TestPersistence:
    """Verify state survives save/load cycle."""

    def test_persist_and_reload(self, storage):
        mgr1 = StateManager(storage)
        failure = VerificationFailure(
            FailureType.HASH_MISMATCH, 1, "mismatch"
        )
        result = _make_result(healthy=False, failures=[failure])
        mgr1.update_verification(result)
        mgr1.set_frozen(True)

        # Create new instance and load from disk
        mgr2 = StateManager(storage)
        mgr2.load_from_disk()

        assert mgr2.get_health_status() == "broken"
        assert mgr2.get_state()["frozen"] is True
        assert mgr2.get_state()["total_verifications"] == 1

    def test_load_from_empty_disk(self, storage):
        """Loading with no state file leaves defaults."""
        mgr = StateManager(storage)
        mgr.load_from_disk()
        assert mgr.get_health_status() == "healthy"
