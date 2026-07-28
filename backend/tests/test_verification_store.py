"""
Tests for the verification history store.
"""

import pytest

from backend.core.normalizer import reset_event_counter
from backend.core.storage import Storage
from backend.core.verification_store import VerificationStore
from backend.core.verifier import (
    VerificationResult,
    VerificationFailure,
    FailureType,
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
def store(storage):
    return VerificationStore(storage)


def _make_result(ver_id: str = "ver-000001", healthy: bool = True) -> VerificationResult:
    return VerificationResult(
        verification_id=ver_id,
        healthy=healthy,
        blocks_checked=5,
        first_invalid_index=None if healthy else 1,
        failures=[] if healthy else [
            VerificationFailure(FailureType.HASH_MISMATCH, 1, "test")
        ],
        timestamp_utc="2026-07-16T12:00:00.000Z",
        duration_ms=1.5,
    )


# ── Save and read ────────────────────────────────────────────────────


class TestSaveAndRead:
    """Verify save + read roundtrip."""

    def test_save_and_read_single(self, store):
        result = _make_result()
        store.save_result(result)

        history = store.read_history()
        assert len(history) == 1
        assert history[0]["verification_id"] == "ver-000001"
        assert history[0]["healthy"] is True

    def test_save_multiple_and_read(self, store):
        store.save_result(_make_result("ver-000001"))
        store.save_result(_make_result("ver-000002"))
        store.save_result(_make_result("ver-000003"))

        history = store.read_history()
        assert len(history) == 3
        # Newest first
        assert history[0]["verification_id"] == "ver-000003"
        assert history[2]["verification_id"] == "ver-000001"

    def test_roundtrip_preserves_failures(self, store):
        result = _make_result("ver-000001", healthy=False)
        store.save_result(result)

        history = store.read_history()
        assert history[0]["healthy"] is False
        assert len(history[0]["failures"]) == 1
        assert history[0]["failures"][0]["failure_type"] == "hash_mismatch"

    def test_roundtrip_preserves_duration(self, store):
        result = _make_result()
        store.save_result(result)

        history = store.read_history()
        assert history[0]["duration_ms"] == 1.5


# ── Empty history ────────────────────────────────────────────────────


class TestEmptyHistory:
    """Verify behaviour with no history."""

    def test_empty_read(self, store):
        assert store.read_history() == []

    def test_empty_with_limit(self, store):
        assert store.read_history(limit=10) == []


# ── History limit ────────────────────────────────────────────────────


class TestHistoryLimit:
    """Verify the limit parameter works correctly."""

    def test_limit_returns_most_recent(self, store):
        for i in range(10):
            store.save_result(_make_result(f"ver-{i:06d}"))

        history = store.read_history(limit=3)
        assert len(history) == 3
        # Newest first
        assert history[0]["verification_id"] == "ver-000009"

    def test_limit_larger_than_history(self, store):
        store.save_result(_make_result("ver-000001"))
        store.save_result(_make_result("ver-000002"))

        history = store.read_history(limit=100)
        assert len(history) == 2

    def test_limit_zero_returns_empty(self, store):
        store.save_result(_make_result())
        history = store.read_history(limit=0)
        assert history == []
