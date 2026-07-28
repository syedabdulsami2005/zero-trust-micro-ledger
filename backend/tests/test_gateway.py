"""
Tests for the Local Communication Gateway (Phase 3).

Spins up a real GatewayServer on a random loopback port for each test
module and fires HTTP requests via urllib (stdlib).  All tests run in
isolated temporary directories so they never touch production ledger data.

Test groups:
  - Health          (2 tests)
  - State           (3 tests)
  - Files           (2 tests)
  - Events          (3 tests)
  - Ledger list     (5 tests)
  - Ledger block    (2 tests)
  - Verification    (3 tests)
  - Alerts          (3 tests)
  - Run-verify      (3 tests)
  - Exports         (5 tests)
  - CORS            (1 test)
  - Errors          (3 tests)
                   ──────────
  Total:           35 tests
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from backend.core.alert_store import AlertStore
from backend.core.ledger_engine import LedgerEngine
from backend.core.state_manager import StateManager
from backend.core.storage import Storage
from backend.core.verification_store import VerificationStore
from backend.daemon.daemon import VerificationDaemon
from backend.gateway.context import GatewayContext
from backend.gateway.server import GatewayServer


# ── Helpers ───────────────────────────────────────────────────────────────────


def _free_port() -> int:
    """Find a free loopback port the OS will let us bind."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str, *, expect_status: int = 200) -> dict:
    """GET *url* and return the parsed JSON body."""
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == expect_status, f"Expected {expect_status}, got {resp.status}"
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == expect_status:
            return json.loads(exc.read())
        raise


def _post(url: str, body: dict | None = None, *, expect_status: int = 200) -> dict:
    """POST *url* with optional JSON body and return the parsed JSON response."""
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == expect_status, f"Expected {expect_status}, got {resp.status}"
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == expect_status:
            return json.loads(exc.read())
        raise


def _wait_for_server(base_url: str, retries: int = 20, delay: float = 0.05) -> None:
    """Poll /api/health until the server is up or we give up."""
    for _ in range(retries):
        try:
            urllib.request.urlopen(f"{base_url}/api/health", timeout=1)
            return
        except Exception:
            time.sleep(delay)
    raise RuntimeError(f"Gateway did not start at {base_url}")


def _sample_event(n: int = 1) -> dict:
    return {
        "event_type": "file_modified",
        "source_type": "config_file",
        "source_path": f"/etc/device{n}.conf",
        "log_data": {
            "summary": f"change {n}",
            "raw_line": None,
            "snapshot_sha256": "a" * 64,
            "metadata": {"actor": "test", "encoding": "utf-8", "size_bytes": 100},
        },
    }


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def gateway_env(tmp_path_factory):
    """
    Module-scoped fixture: one server shared by all tests in this file.

    Starts with a fresh ledger containing genesis + 3 appended events.
    """
    data_dir = tmp_path_factory.mktemp("ledger_gw")
    storage = Storage(data_dir)
    engine = LedgerEngine(storage)
    engine.initialize()

    # Append 3 events so tests have data to query
    for i in range(1, 4):
        engine.append_event(_sample_event(i))

    alert_store = AlertStore(storage.ledger_dir)
    state_manager = StateManager(storage, alert_store=alert_store)
    verification_store = VerificationStore(storage)
    daemon = VerificationDaemon(
        engine=engine,
        storage=storage,
        state_manager=state_manager,
        verification_store=verification_store,
        alert_store=alert_store,
        interval_seconds=9999,  # do not run automatically
    )

    port = _free_port()
    ctx = GatewayContext(
        engine=engine,
        storage=storage,
        state_manager=state_manager,
        verification_store=verification_store,
        daemon=daemon,
        alert_store=alert_store,
    )
    server = GatewayServer(ctx, host="127.0.0.1", port=port)
    server.start()
    _wait_for_server(server.base_url)

    yield server  # tests receive the GatewayServer instance

    server.stop()


@pytest.fixture()
def base(gateway_env):
    """Shortcut: return the base URL string."""
    return gateway_env.base_url


# ── Health (2 tests) ──────────────────────────────────────────────────────────


class TestHealth:
    def test_health_returns_200(self, base):
        data = _get(f"{base}/api/health")
        assert data["status"] == "ok"

    def test_health_has_timestamp(self, base):
        data = _get(f"{base}/api/health")
        assert "timestamp_utc" in data
        assert isinstance(data["timestamp_utc"], str)


# ── State (3 tests) ───────────────────────────────────────────────────────────


class TestState:
    def test_state_returns_200(self, base):
        data = _get(f"{base}/api/state")
        assert isinstance(data, dict)

    def test_state_has_health_status(self, base):
        data = _get(f"{base}/api/state")
        assert "health_status" in data
        assert data["health_status"] in ("healthy", "degraded", "broken")

    def test_state_has_frozen_field(self, base):
        data = _get(f"{base}/api/state")
        assert "frozen" in data
        assert isinstance(data["frozen"], bool)


# ── Files (2 tests) ───────────────────────────────────────────────────────────


class TestFiles:
    def test_files_returns_list(self, base):
        data = _get(f"{base}/api/files")
        assert isinstance(data, list)

    def test_files_entries_have_source_path(self, base):
        data = _get(f"{base}/api/files")
        # We appended 3 events with distinct source_paths
        assert len(data) >= 3
        for entry in data:
            assert "source_path" in entry
            assert "event_count" in entry


# ── Events (3 tests) ──────────────────────────────────────────────────────────


class TestEvents:
    def test_events_returns_list(self, base):
        data = _get(f"{base}/api/events")
        assert isinstance(data, list)

    def test_events_excludes_genesis(self, base):
        data = _get(f"{base}/api/events")
        for ev in data:
            assert ev["event_type"] != "system_genesis"

    def test_events_limit_param(self, base):
        data = _get(f"{base}/api/events?limit=1")
        assert len(data) <= 1


# ── Ledger list (5 tests) ─────────────────────────────────────────────────────


class TestLedgerList:
    def test_ledger_returns_dict(self, base):
        data = _get(f"{base}/api/ledger")
        assert isinstance(data, dict)
        assert "blocks" in data
        assert "total" in data

    def test_ledger_total_includes_genesis(self, base):
        data = _get(f"{base}/api/ledger")
        # genesis + 3 events = 4
        assert data["total"] == 4

    def test_ledger_default_limit_50(self, base):
        data = _get(f"{base}/api/ledger")
        assert data["limit"] == 50

    def test_ledger_pagination_offset(self, base):
        data = _get(f"{base}/api/ledger?offset=2&limit=2")
        assert data["offset"] == 2
        assert len(data["blocks"]) == 2

    def test_ledger_blocks_have_required_fields(self, base):
        data = _get(f"{base}/api/ledger")
        for block in data["blocks"]:
            assert "block_index" in block
            assert "current_hash" in block
            assert "previous_hash" in block


# ── Ledger block (2 tests) ────────────────────────────────────────────────────


class TestLedgerBlock:
    def test_ledger_block_by_index(self, base):
        block = _get(f"{base}/api/ledger/0")
        assert block["block_index"] == 0
        assert block["event_type"] == "genesis"

    def test_ledger_block_not_found(self, base):
        err = _get(f"{base}/api/ledger/9999", expect_status=404)
        assert err["code"] == 404
        assert "error" in err


# ── Verification (3 tests) ────────────────────────────────────────────────────


class TestVerification:
    def test_verification_returns_list(self, base):
        # Trigger a run first so history is non-empty
        _post(f"{base}/api/actions/run-verification")
        data = _get(f"{base}/api/verification")
        assert isinstance(data, list)

    def test_verification_entry_has_required_fields(self, base):
        _post(f"{base}/api/actions/run-verification")
        data = _get(f"{base}/api/verification")
        assert len(data) >= 1
        entry = data[0]
        assert "verification_id" in entry
        assert "healthy" in entry
        assert "blocks_checked" in entry

    def test_verification_limit_param(self, base):
        data = _get(f"{base}/api/verification?limit=1")
        assert len(data) <= 1


# ── Alerts (3 tests) ──────────────────────────────────────────────────────────


class TestAlerts:
    def test_alerts_returns_list(self, base):
        data = _get(f"{base}/api/alerts")
        assert isinstance(data, list)

    def test_alerts_limit_param(self, base):
        data = _get(f"{base}/api/alerts?limit=1")
        assert len(data) <= 1

    def test_alerts_have_alert_id_when_present(self, base):
        data = _get(f"{base}/api/alerts")
        for alert in data:
            assert "alert_id" in alert
            assert "severity" in alert


# ── Run-verification (3 tests) ────────────────────────────────────────────────


class TestRunVerification:
    def test_run_verification_returns_result(self, base):
        data = _post(f"{base}/api/actions/run-verification")
        assert "verification_id" in data
        assert "healthy" in data
        assert "blocks_checked" in data

    def test_run_verification_blocks_checked_equals_chain(self, base):
        data = _post(f"{base}/api/actions/run-verification")
        # genesis + 3 events = 4 blocks
        assert data["blocks_checked"] == 4

    def test_run_verification_get_not_allowed(self, base):
        err = _get(f"{base}/api/actions/run-verification", expect_status=405)
        assert err["code"] == 405


# ── Exports (5 tests) ─────────────────────────────────────────────────────────


class TestExports:
    def test_export_full(self, base):
        data = _post(f"{base}/api/exports", {"type": "full"})
        assert data["type"] == "full"
        assert "export_id" in data
        assert "exported_at" in data
        assert data["record_count"] == 4  # genesis + 3 events

    def test_export_events(self, base):
        data = _post(f"{base}/api/exports", {"type": "events"})
        assert data["type"] == "events"
        # 3 non-genesis events
        assert data["record_count"] == 3

    def test_export_alerts(self, base):
        data = _post(f"{base}/api/exports", {"type": "alerts"})
        assert data["type"] == "alerts"
        assert isinstance(data["data"], list)

    def test_export_verification(self, base):
        data = _post(f"{base}/api/exports", {"type": "verification"})
        assert data["type"] == "verification"
        assert isinstance(data["data"], list)

    def test_export_invalid_type_returns_400(self, base):
        err = _post(f"{base}/api/exports", {"type": "invalid_type"}, expect_status=400)
        assert err["code"] == 400


# ── CORS (1 test) ─────────────────────────────────────────────────────────────


class TestCORS:
    def test_cors_header_present(self, base):
        req = urllib.request.Request(f"{base}/api/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"


# ── Error handling (3 tests) ──────────────────────────────────────────────────


class TestErrors:
    def test_unknown_route_404(self, base):
        err = _get(f"{base}/api/nonexistent", expect_status=404)
        assert err["code"] == 404
        assert "error" in err

    def test_post_on_get_route_405(self, base):
        err = _post(f"{base}/api/state", expect_status=405)
        assert err["code"] == 405

    def test_ledger_block_non_numeric_index_404(self, base):
        # /api/ledger/abc — doesn't match the int pattern → 404
        err = _get(f"{base}/api/ledger/abc", expect_status=404)
        assert err["code"] == 404
