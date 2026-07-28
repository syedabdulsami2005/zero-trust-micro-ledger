"""Tests for the deterministic event normalizer."""

import re
import pytest

from backend.core.normalizer import (
    NormalizationError,
    normalize_event,
    reset_event_counter,
    _normalize_timestamp,
    _sanitize_text,
)


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_counter():
    """Reset the global event counter before each test."""
    reset_event_counter(0)
    yield
    reset_event_counter(0)


def _minimal_raw_event(**overrides) -> dict:
    """Return a minimal valid raw event with optional overrides."""
    base = {
        "event_type": "file_modified",
        "source_type": "config_file",
        "source_path": "/etc/device.conf",
    }
    base.update(overrides)
    return base


# ── Timestamp normalisation ───────────────────────────────────────────

class TestTimestampNormalization:
    def test_none_generates_utc_now(self):
        ts = _normalize_timestamp(None)
        assert ts.endswith("Z")
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", ts)

    def test_iso_string_with_z(self):
        ts = _normalize_timestamp("2026-07-15T14:22:14.123Z")
        assert ts == "2026-07-15T14:22:14.123Z"

    def test_iso_string_with_offset(self):
        ts = _normalize_timestamp("2026-07-15T16:22:14.123+02:00")
        assert ts == "2026-07-15T14:22:14.123Z"

    def test_naive_datetime_assumed_utc(self):
        from datetime import datetime
        dt = datetime(2026, 7, 15, 14, 22, 14, 123000)
        ts = _normalize_timestamp(dt)
        assert ts == "2026-07-15T14:22:14.123Z"

    def test_invalid_string_raises(self):
        with pytest.raises(NormalizationError, match="Unparseable"):
            _normalize_timestamp("not-a-date")

    def test_unsupported_type_raises(self):
        with pytest.raises(NormalizationError, match="Unsupported"):
            _normalize_timestamp(12345)


# ── Text sanitisation ─────────────────────────────────────────────────

class TestSanitizeText:
    def test_none_passthrough(self):
        assert _sanitize_text(None) is None

    def test_bytes_decoded_utf8(self):
        assert _sanitize_text(b"hello") == "hello"

    def test_invalid_bytes_replaced(self):
        result = _sanitize_text(b"bad\xff\xfebytes")
        assert result is not None
        assert "\ufffd" in result  # replacement character

    def test_crlf_normalized(self):
        assert _sanitize_text("line1\r\nline2\rline3") == "line1\nline2\nline3"


# ── Event normalisation ───────────────────────────────────────────────

class TestNormalizeEvent:
    def test_minimal_event_succeeds(self):
        result = normalize_event(_minimal_raw_event())
        assert result["event_type"] == "file_modified"
        assert result["source_type"] == "config_file"
        assert result["source_path"] == "/etc/device.conf"
        assert result["source_identifier"] == "device.conf"
        assert result["timestamp_utc"].endswith("Z")
        assert result["event_id"] == "evt-000001"
        assert isinstance(result["log_data"], dict)

    def test_missing_required_field_raises(self):
        with pytest.raises(NormalizationError, match="Missing required"):
            normalize_event({"event_type": "file_modified"})

    def test_invalid_event_type_raises(self):
        with pytest.raises(NormalizationError, match="Invalid event_type"):
            normalize_event(_minimal_raw_event(event_type="bogus"))

    def test_invalid_source_type_raises(self):
        with pytest.raises(NormalizationError, match="Invalid source_type"):
            normalize_event(_minimal_raw_event(source_type="bogus"))

    def test_non_dict_raises(self):
        with pytest.raises(NormalizationError, match="must be a dict"):
            normalize_event("not a dict")

    def test_event_id_auto_generated(self):
        e1 = normalize_event(_minimal_raw_event())
        e2 = normalize_event(_minimal_raw_event())
        assert e1["event_id"] == "evt-000001"
        assert e2["event_id"] == "evt-000002"

    def test_explicit_event_id_preserved(self):
        result = normalize_event(_minimal_raw_event(event_id="evt-custom"))
        assert result["event_id"] == "evt-custom"

    def test_source_identifier_derived_from_path(self):
        result = normalize_event(
            _minimal_raw_event(source_path="/var/log/syslog")
        )
        assert result["source_identifier"] == "syslog"

    def test_explicit_source_identifier_preserved(self):
        result = normalize_event(
            _minimal_raw_event(source_identifier="custom-name")
        )
        assert result["source_identifier"] == "custom-name"

    def test_log_data_defaults(self):
        result = normalize_event(_minimal_raw_event())
        ld = result["log_data"]
        assert ld["summary"] is None
        assert ld["raw_line"] is None
        assert ld["snapshot_sha256"] is None
        assert isinstance(ld["metadata"], dict)
        assert ld["metadata"]["actor"] == "system"

    def test_log_data_with_content(self):
        raw = _minimal_raw_event(
            log_data={
                "summary": "config changed",
                "raw_line": "key=value",
                "snapshot_sha256": "abc123",
                "metadata": {"actor": "admin", "size_bytes": 256},
            }
        )
        result = normalize_event(raw)
        ld = result["log_data"]
        assert ld["summary"] == "config changed"
        assert ld["raw_line"] == "key=value"
        assert ld["snapshot_sha256"] == "abc123"
        assert ld["metadata"]["actor"] == "admin"
        assert ld["metadata"]["size_bytes"] == 256

    def test_idempotency(self):
        """Same input (with fixed timestamp and event_id) produces same output."""
        raw = _minimal_raw_event(
            timestamp_utc="2026-07-15T14:22:14.123Z",
            event_id="evt-fixed",
        )
        r1 = normalize_event(raw)
        r2 = normalize_event(raw)
        assert r1 == r2
