"""
Centralised runtime state manager.

Owns the ``state.json`` lifecycle and exposes thread-safe read/write
for chain health status, verification history, freeze state, and
alert counts.

Chain state model (deterministic state machine):
  - ``healthy`` : last verification passed, chain intact, appends active
  - ``broken``  : hash or link mismatch detected, chain compromised, appends frozen
  - ``degraded`` : minor issues (schema warnings, segment mismatch)

Transitions (backend-only — never driven from the frontend):
  verification fails  → chain_state = broken, append_enabled = false
  verification passes AND was broken → chain_state = healthy, append_enabled = true
  verification passes AND was healthy → no state change needed
"""

import threading
from collections import deque

from backend.core.normalizer import _normalize_timestamp
from backend.core.storage import Storage
from backend.core.verifier import VerificationResult, FailureType


# Failure types that indicate a fully broken chain
_BREAKING_FAILURES = frozenset({
    FailureType.HASH_MISMATCH,
    FailureType.PREVIOUS_HASH_MISMATCH,
})

# Maximum verification history entries kept in memory
MAX_HISTORY = 50


class StateManager:
    """
    Thread-safe runtime state tracker with full alert lifecycle integration.

    Parameters
    ----------
    storage : Storage
        Storage backend for persisting state to disk.
    alert_store : AlertStore | None
        Alert lifecycle store. If None, counts are not tracked.
    """

    def __init__(self, storage: Storage, alert_store=None) -> None:
        self._storage = storage
        self._alert_store = alert_store
        self._lock = threading.Lock()

        # Chain state fields
        self._chain_state: str = "healthy"     # healthy | broken | degraded
        self._append_enabled: bool = True
        self._frozen: bool = False              # legacy alias for append_enabled=False

        # Verification tracking
        self._last_verification_utc: str | None = None
        self._last_verification_result: str = "pass"  # pass | fail
        self._first_invalid_block: int | None = None
        self._total_verifications: int = 0
        self._history: deque[dict] = deque(maxlen=MAX_HISTORY)

        # Resolved incident tracking
        self._last_resolved_incident: dict | None = None

        # Previous chain state (for transition detection)
        self._previous_chain_state: str = "healthy"

    # ── State machine ──────────────────────────────────────────────────

    def update_verification(self, result: VerificationResult) -> dict:
        """
        Apply the verification state machine.

        Parameters
        ----------
        result : VerificationResult
            The completed verification run.

        Returns
        -------
        dict
            A dict describing what state transitions occurred:
            ``{chain_restored: bool, resolved_alert_ids: list[str]}``.
        """
        with self._lock:
            self._total_verifications += 1
            self._last_verification_utc = result.timestamp_utc

            failure_types = {f.failure_type for f in result.failures}
            was_broken = self._chain_state == "broken"
            resolved_ids: list[str] = []
            chain_restored = False

            if failure_types & _BREAKING_FAILURES:
                # Chain is broken
                self._chain_state = "broken"
                self._append_enabled = False
                self._frozen = True
                self._last_verification_result = "fail"
                if result.first_invalid_index is not None:
                    self._first_invalid_block = result.first_invalid_index

            elif failure_types:
                # Degraded — minor issues only
                self._chain_state = "degraded"
                self._append_enabled = True
                self._frozen = False
                self._last_verification_result = "fail"

            else:
                # Clean pass
                self._last_verification_result = "pass"
                if was_broken:
                    # TRANSITION: broken → healthy
                    self._chain_state = "healthy"
                    self._append_enabled = True
                    self._frozen = False
                    self._first_invalid_block = None
                    chain_restored = True

                    # Auto-resolve all unresolved alerts
                    if self._alert_store is not None:
                        resolved_ids = self._alert_store.resolve_all_unresolved(
                            result.verification_id
                        )
                        last_resolved = self._alert_store.get_last_resolved()
                        if last_resolved:
                            self._last_resolved_incident = last_resolved
                else:
                    # Already healthy — but resolve any stale active alerts from prior sessions.
                    # This handles the startup reconciliation case: chain was repaired externally
                    # before this session, so active alerts are now stale.
                    self._chain_state = "healthy"
                    self._append_enabled = True
                    self._frozen = False
                    if self._alert_store is not None:
                        stale = self._alert_store.get_active_alerts()
                        if stale:
                            resolved_ids = self._alert_store.resolve_all_unresolved(
                                result.verification_id
                            )
                            if resolved_ids:
                                chain_restored = True  # signal unfreeze just in case
                                last_resolved = self._alert_store.get_last_resolved()
                                if last_resolved:
                                    self._last_resolved_incident = last_resolved


            self._history.append(result.to_dict())
            self._persist()

        return {
            "chain_restored": chain_restored,
            "resolved_alert_ids": resolved_ids,
        }

    def set_frozen(self, frozen: bool) -> None:
        """Update the freeze state (called by daemon for explicit freeze/unfreeze)."""
        with self._lock:
            self._frozen = frozen
            self._append_enabled = not frozen
            if not frozen and self._chain_state == "broken":
                # Only set healthy if explicitly unfreezing after a repair
                pass  # Let update_verification drive the state transition
            self._persist()

    def get_health_status(self) -> str:
        """Return current health status: healthy | degraded | broken."""
        with self._lock:
            return self._chain_state

    def _get_alert_counts(self) -> dict[str, int]:
        """Get alert counts from the alert store, or zeros if unavailable."""
        if self._alert_store is not None:
            return self._alert_store.get_counts()
        return {"active": 0, "acknowledged": 0, "resolved": 0, "total": 0}

    def _build_state_dict(self) -> dict:
        """Construct the state dictionary. Caller must hold ``_lock``."""
        counts = self._get_alert_counts()
        return {
            # New canonical fields
            "chain_state": self._chain_state,
            "append_enabled": self._append_enabled,
            "active_alert_count": counts["active"],
            "acknowledged_alert_count": counts["acknowledged"],
            "resolved_alert_count": counts["resolved"],
            "last_verification_result": self._last_verification_result,
            "first_invalid_block": self._first_invalid_block,
            "last_resolved_incident": self._last_resolved_incident,
            # Timing
            "last_verification_utc": self._last_verification_utc,
            "last_verified_at": self._last_verification_utc,
            "total_verifications": self._total_verifications,
            "updated_utc": _normalize_timestamp(None),
            # Legacy compat fields
            "health_status": self._chain_state,
            "frozen": self._frozen,
            "daemon_status": "running",
        }

    def get_state(self) -> dict:
        """
        Return a snapshot of the full runtime state.

        Returns
        -------
        dict
            Complete state suitable for API responses and persistence.
        """
        with self._lock:
            return self._build_state_dict()

    def get_history(self) -> list[dict]:
        """Return verification history (newest first)."""
        with self._lock:
            return list(reversed(self._history))

    def get_chain_state(self) -> str:
        """Return the current chain state."""
        with self._lock:
            return self._chain_state

    def is_append_enabled(self) -> bool:
        """Return True if append operations are currently allowed."""
        with self._lock:
            return self._append_enabled

    def load_from_disk(self) -> None:
        """
        Restore state from the persisted state file on startup.

        Tolerant of missing or incomplete state files.
        """
        with self._lock:
            saved = self._storage.load_state()
            if saved is None:
                return
            # Support both old and new field names
            self._chain_state = (
                saved.get("chain_state")
                or saved.get("health_status", "healthy")
            )
            self._frozen = saved.get("frozen", False)
            self._append_enabled = saved.get("append_enabled", not self._frozen)
            self._last_verification_utc = saved.get(
                "last_verification_utc") or saved.get("last_verified_at")
            self._last_verification_result = saved.get("last_verification_result", "pass")
            self._first_invalid_block = saved.get("first_invalid_block")
            self._total_verifications = saved.get("total_verifications", 0)
            self._last_resolved_incident = saved.get("last_resolved_incident")

    def _persist(self) -> None:
        """Write current state to disk. Caller must hold ``_lock``."""
        self._storage.save_state(self._build_state_dict())
