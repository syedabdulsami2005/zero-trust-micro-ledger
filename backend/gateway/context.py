"""
Gateway context.

A plain dataclass that bundles all backend references the HTTP
request handler needs.  Passed once at server construction time
so no module-level globals are needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.core.alert_store import AlertStore
from backend.core.ledger_engine import LedgerEngine
from backend.core.state_manager import StateManager
from backend.core.storage import Storage
from backend.core.verification_store import VerificationStore
from backend.daemon.daemon import VerificationDaemon


@dataclass
class GatewayContext:
    """
    Shared backend references for the HTTP request handler.

    Parameters
    ----------
    engine : LedgerEngine
        The single-writer ledger engine.
    storage : Storage
        Storage backend (blocks, alerts, state files).
    state_manager : StateManager
        Runtime state tracker.
    verification_store : VerificationStore
        Persistent verification history.
    daemon : VerificationDaemon
        Background verification daemon (used for manual trigger and
        is_running status).
    alert_store : AlertStore
        Mutable alert lifecycle index (deduplication + status updates).
    watcher : Any | None
        Background source watcher daemon for capturing file snapshots.
    """

    engine: LedgerEngine
    storage: Storage
    state_manager: StateManager
    verification_store: VerificationStore
    daemon: VerificationDaemon
    alert_store: AlertStore = field(default_factory=lambda: None)  # type: ignore[assignment]
    watcher: Any | None = None
