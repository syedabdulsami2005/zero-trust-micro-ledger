"""
Tests for the alert generation module.
"""

import pytest

from backend.core.alerts import (
    create_alert,
    create_alerts_from_result,
    _SEVERITY_MAP,
    _ALERT_TYPE_MAP,
    reset_alert_counter,
)
from backend.core.verifier import (
    FailureType,
    VerificationFailure,
    VerificationResult,
    reset_verification_counter,
)
from backend.core.normalizer import reset_event_counter


@pytest.fixture(autouse=True)
def _reset_counters():
    """Reset all global counters before each test."""
    reset_alert_counter(0)
    reset_verification_counter(0)
    reset_event_counter(0)


def _make_failure(
    ftype: FailureType = FailureType.HASH_MISMATCH,
    block_index: int | None = 1,
    msg: str = "test failure",
) -> VerificationFailure:
    return VerificationFailure(
        failure_type=ftype,
        block_index=block_index,
        message=msg,
        details={"key": "val"},
    )


def _make_result(
    failures: list[VerificationFailure] | None = None,
) -> VerificationResult:
    if failures is None:
        failures = []
    return VerificationResult(
        verification_id="ver-000001",
        healthy=len(failures) == 0,
        blocks_checked=5,
        first_invalid_index=failures[0].block_index if failures else None,
        failures=failures,
        timestamp_utc="2026-07-16T12:00:00.000Z",
        duration_ms=1.5,
    )


# ── Severity mapping ─────────────────────────────────────────────────


class TestSeverityMapping:
    """Verify correct severity for each failure type."""

    def test_hash_mismatch_is_critical(self):
        assert _SEVERITY_MAP.get(FailureType.HASH_MISMATCH) == "critical"

    def test_previous_hash_mismatch_is_critical(self):
        assert _SEVERITY_MAP.get(FailureType.PREVIOUS_HASH_MISMATCH) == "critical"

    def test_index_gap_is_warning(self):
        assert _SEVERITY_MAP.get(FailureType.INDEX_GAP) == "warning"

    def test_index_duplicate_is_warning(self):
        assert _SEVERITY_MAP.get(FailureType.INDEX_DUPLICATE) == "warning"

    def test_truncation_is_warning(self):
        assert _SEVERITY_MAP.get(FailureType.TRUNCATION) == "warning"

    def test_segment_inconsistency_is_warning(self):
        assert _SEVERITY_MAP.get(FailureType.SEGMENT_INCONSISTENCY) == "warning"

    def test_schema_invalid_is_info(self):
        assert _SEVERITY_MAP.get(FailureType.SCHEMA_INVALID, "info") == "info"


# ── Alert type mapping ───────────────────────────────────────────────


class TestAlertTypeMapping:
    """Verify correct alert_type for each failure type."""

    def test_hash_mismatch_chain_break(self):
        assert _ALERT_TYPE_MAP.get(FailureType.HASH_MISMATCH) == "chain_break"

    def test_previous_hash_chain_break(self):
        assert _ALERT_TYPE_MAP.get(FailureType.PREVIOUS_HASH_MISMATCH) == "chain_break"

    def test_truncation_type(self):
        assert _ALERT_TYPE_MAP.get(FailureType.TRUNCATION) == "truncation"

    def test_segment_error_type(self):
        assert _ALERT_TYPE_MAP.get(FailureType.SEGMENT_INCONSISTENCY) == "segment_error"

    def test_schema_violation_type(self):
        assert _ALERT_TYPE_MAP.get(FailureType.SCHEMA_INVALID) == "schema_violation"


# ── Alert creation ───────────────────────────────────────────────────


class TestCreateAlert:
    """Verify the structure of created alert dicts."""

    def test_alert_has_required_fields(self):
        failure = _make_failure()
        alert = create_alert(failure, "ver-000001")

        assert "alert_id" in alert
        assert "timestamp_utc" in alert
        assert "severity" in alert
        assert "alert_type" in alert
        assert "message" in alert
        assert "details" in alert
        assert "verification_id" in alert
        assert "acknowledged" in alert

    def test_alert_id_format(self):
        failure = _make_failure()
        alert = create_alert(failure, "ver-000001")
        assert alert["alert_id"].startswith("alt-")

    def test_alert_timestamp_format(self):
        failure = _make_failure()
        alert = create_alert(failure, "ver-000001")
        assert alert["timestamp_utc"].endswith("Z")

    def test_alert_not_acknowledged_by_default(self):
        failure = _make_failure()
        alert = create_alert(failure, "ver-000001")
        assert alert["acknowledged"] is False

    def test_alert_carries_verification_id(self):
        failure = _make_failure()
        alert = create_alert(failure, "ver-000042")
        assert alert["verification_id"] == "ver-000042"

    def test_alert_details_include_block_index(self):
        failure = _make_failure(block_index=7)
        alert = create_alert(failure, "ver-000001")
        assert alert["details"]["block_index"] == 7

    def test_alert_details_include_failure_type(self):
        failure = _make_failure(ftype=FailureType.TRUNCATION)
        alert = create_alert(failure, "ver-000001")
        assert alert["details"]["failure_type"] == "truncation"

    def test_alert_details_include_original_details(self):
        failure = _make_failure()
        alert = create_alert(failure, "ver-000001")
        assert alert["details"]["key"] == "val"

    def test_critical_severity_for_hash_mismatch(self):
        failure = _make_failure(ftype=FailureType.HASH_MISMATCH)
        alert = create_alert(failure, "ver-000001")
        assert alert["severity"] == "critical"

    def test_warning_severity_for_index_gap(self):
        failure = _make_failure(ftype=FailureType.INDEX_GAP)
        alert = create_alert(failure, "ver-000001")
        assert alert["severity"] == "warning"

    def test_info_severity_for_schema_invalid(self):
        failure = _make_failure(ftype=FailureType.SCHEMA_INVALID)
        alert = create_alert(failure, "ver-000001")
        assert alert["severity"] == "info"


# ── Monotonic alert IDs ──────────────────────────────────────────────


class TestAlertIdMonotonicity:
    """Alert IDs must increase monotonically."""

    def test_sequential_ids(self):
        f1 = _make_failure()
        f2 = _make_failure(block_index=2)
        a1 = create_alert(f1, "ver-000001")
        a2 = create_alert(f2, "ver-000001")

        id1 = int(a1["alert_id"].split("-")[1])
        id2 = int(a2["alert_id"].split("-")[1])
        assert id2 > id1


# ── Batch alert creation ─────────────────────────────────────────────


class TestCreateAlertsFromResult:
    """Verify batch alert creation from VerificationResult."""

    def test_empty_failures_no_alerts(self):
        result = _make_result([])
        alerts = create_alerts_from_result(result)
        assert alerts == []

    def test_one_failure_one_alert(self):
        result = _make_result([_make_failure()])
        alerts = create_alerts_from_result(result)
        assert len(alerts) == 1

    def test_multiple_failures_multiple_alerts(self):
        failures = [
            _make_failure(FailureType.HASH_MISMATCH, 1),
            _make_failure(FailureType.INDEX_GAP, 3),
            _make_failure(FailureType.TRUNCATION, None, "truncated"),
        ]
        result = _make_result(failures)
        alerts = create_alerts_from_result(result)
        assert len(alerts) == 3

    def test_alerts_reference_correct_verification_id(self):
        result = _make_result([_make_failure()])
        alerts = create_alerts_from_result(result)
        assert alerts[0]["verification_id"] == "ver-000001"
