"""
Background integrity verification daemon.

Runs a periodic verification loop in a daemon thread. When the
chain is found to be unhealthy:
  1. Generates deduplicated structured alerts for each new failure
  2. Persists alerts via AlertStore (deduplication) and Storage (audit log)
  3. Freezes the ledger engine (Rule 2)
  4. Updates the state manager

When a subsequent clean pass follows a broken state:
  1. State manager auto-resolves unresolved alerts
  2. Engine is unfrozen
  3. Append operations resume

The daemon is robust per Rule 3 — catches all exceptions in the
loop body so it never crashes the host process.
"""

import logging
import threading
import time

from backend.core.alerts import create_alerts_from_result
from backend.core.alert_store import AlertStore
from backend.core.ledger_engine import LedgerEngine
from backend.core.state_manager import StateManager
from backend.core.storage import Storage
from backend.core.verifier import verify_chain, VerificationResult
from backend.core.verification_store import VerificationStore


logger = logging.getLogger(__name__)


class VerificationDaemon:
    """
    Background verification loop.

    Runs ``verify_chain`` at a configurable interval in a daemon
    thread. On failure, freezes the engine and generates deduplicated
    alerts. On clean recovery, unfreezes automatically.

    Parameters
    ----------
    engine : LedgerEngine
        The ledger engine to freeze/unfreeze on chain state changes.
    storage : Storage
        Storage backend for reading blocks and writing audit alerts.
    state_manager : StateManager
        Runtime state tracker (owns the state machine).
    verification_store : VerificationStore
        Persistent verification history.
    alert_store : AlertStore
        Mutable alert lifecycle index (deduplication + status updates).
    interval_seconds : float
        Seconds between verification passes (default 30).
    """

    def __init__(
        self,
        engine: LedgerEngine,
        storage: Storage,
        state_manager: StateManager,
        verification_store: VerificationStore,
        alert_store: AlertStore,
        interval_seconds: float = 30.0,
    ) -> None:
        self._engine = engine
        self._storage = storage
        self._state_manager = state_manager
        self._verification_store = verification_store
        self._alert_store = alert_store
        self._interval = interval_seconds

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the background verification thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="verification-daemon",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the daemon to stop and wait for the thread to exit."""
        with self._lock:
            if not (self._thread is not None and self._thread.is_alive()):
                return
            self._stop_event.set()
            thread_to_join = self._thread

        if thread_to_join is not None:
            thread_to_join.join(timeout=timeout)

        with self._lock:
            self._thread = None

    def is_running(self) -> bool:
        """Return ``True`` if the daemon loop is active."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        """Main daemon loop. Runs until ``_stop_event`` is set."""
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                # Rule 3: never crash
                logger.exception("Verification loop encountered an error")
            self._stop_event.wait(timeout=self._interval)

    def run_once(self) -> VerificationResult:
        """
        Execute a single verification pass (manual or scheduled trigger).

        Implements the full state machine:
          - Failure: freeze + deduplicated alert upsert
          - Clean pass after broken: unfreeze + auto-resolve alerts

        Can be called from any thread regardless of daemon state.

        Returns
        -------
        VerificationResult
            The result of the verification.
        """
        result = verify_chain(self._storage)

        # Persist verification result
        try:
            self._verification_store.save_result(result)
        except Exception:
            logger.exception("Failed to save verification result")

        # Apply state machine — this handles broken→healthy transition and
        # auto-resolving alerts internally via the AlertStore reference.
        transition = self._state_manager.update_verification(result)

        if not result.healthy:
            # Generate alerts with full lifecycle fields
            alerts = create_alerts_from_result(result)
            for alert in alerts:
                try:
                    # Deduplication: upsert into the live index
                    canonical = self._alert_store.upsert_alert(alert)
                    # Audit log: always append to JSONL (even if deduplicated,
                    # the original event is preserved — but only for NEW alerts)
                    if canonical is alert or canonical.get("alert_id") == alert.get("alert_id"):
                        self._storage.append_alert(alert)
                except Exception:
                    logger.exception("Failed to process alert")

            # Freeze the engine (Rule 2)
            try:
                self._engine.freeze()
            except Exception:
                logger.exception("Failed to freeze engine")

        else:
            # Clean pass — create/update read-only checkpoint
            try:
                self._storage.create_checkpoint(verification_id=result.verification_id)
            except Exception:
                logger.exception("Failed to create backup checkpoint")

            # Check if we just restored from broken state
            if transition.get("chain_restored"):
                try:
                    self._engine.unfreeze()
                    resolved_count = len(transition.get("resolved_alert_ids", []))
                    logger.info(
                        "Chain restored! Unfroze engine. %d alert(s) auto-resolved.",
                        resolved_count,
                    )
                except Exception:
                    logger.exception("Failed to unfreeze engine after recovery")

        return result
