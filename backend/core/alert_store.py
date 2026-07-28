"""
Mutable alert lifecycle index with deduplication.

This module owns the ``alert_index.json`` file — the live working
state of every alert. It is separate from ``alerts.jsonl``, which
is the immutable audit log.

Design rules:
  - ``alerts.jsonl`` is append-only (written by Storage, never touched here).
  - ``alert_index.json`` is a dict keyed by alert_id; written atomically.
  - Deduplication: only one unresolved record per ``incident_key``.
  - Lifecycle transitions: active → acknowledged → resolved.
  - Resolved alerts are never deleted; they remain in the index.
  - Thread-safe via a single ``threading.Lock``.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from backend.core.normalizer import _normalize_timestamp

logger = logging.getLogger(__name__)


class AlertStore:
    """
    Thread-safe alert lifecycle manager.

    Parameters
    ----------
    ledger_dir : Path
        Directory where ``alert_index.json`` is stored.
    """

    def __init__(self, ledger_dir: Path) -> None:
        self._path: Path = ledger_dir / "alert_index.json"
        self._lock = threading.Lock()
        # In-memory index: alert_id -> alert dict
        self._index: dict[str, dict] = {}
        self.load()

    # ── Persistence ────────────────────────────────────────────────────

    def load(self) -> None:
        """Load the alert index from disk. Safe if file does not exist."""
        with self._lock:
            self._load_unlocked()

    def _load_unlocked(self) -> None:
        """Load without acquiring lock. Caller must hold ``_lock``."""
        if not self._path.exists():
            self._index = {}
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._index = data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load alert_index.json: %s — starting empty.", exc)
            self._index = {}

    def _save_unlocked(self) -> None:
        """Atomically write the index to disk. Caller must hold ``_lock``."""
        tmp = self._path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._index, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            for attempt in range(5):
                try:
                    tmp.replace(self._path)
                    return
                except PermissionError:
                    if attempt == 4:
                        raise
                    import time
                    time.sleep(0.05 * (attempt + 1))
        except OSError as exc:
            logger.error("Failed to save alert_index.json: %s", exc)

    # ── Write operations ───────────────────────────────────────────────

    def upsert_alert(self, alert: dict) -> dict:
        """
        Insert a new alert or update an existing unresolved one.

        If an unresolved alert exists for the same ``incident_key``,
        only ``last_seen_at``, ``occurrence_count``, and
        ``verification_id`` are updated (no duplicate created).

        Parameters
        ----------
        alert : dict
            Alert dict from ``create_alert()``.

        Returns
        -------
        dict
            The canonical alert record (new or existing).
        """
        incident_key = alert.get("incident_key", "")
        with self._lock:
            # Search for existing unresolved alert with same incident_key
            existing = self._find_unresolved_by_key_unlocked(incident_key)
            if existing is not None:
                # Deduplicate: update counters only
                existing["occurrence_count"] = existing.get("occurrence_count", 1) + 1
                existing["last_seen_at"] = alert.get("last_seen_at") or _normalize_timestamp(None)
                existing["verification_id"] = alert.get("verification_id", existing["verification_id"])
                self._save_unlocked()
                return existing

            # New incident — insert
            alert_id = alert["alert_id"]
            self._index[alert_id] = dict(alert)
            self._save_unlocked()
            return self._index[alert_id]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Transition an alert from ``active`` → ``acknowledged``.

        Parameters
        ----------
        alert_id : str
            The alert to acknowledge.

        Returns
        -------
        bool
            ``True`` if the alert was found and updated; ``False`` otherwise.
        """
        with self._lock:
            rec = self._index.get(alert_id)
            if rec is None:
                return False
            if rec.get("status") not in ("active",):
                # Already acknowledged or resolved — idempotent success
                return rec.get("status") == "acknowledged"
            rec["status"] = "acknowledged"
            rec["acknowledged"] = True
            rec["acknowledged_at"] = _normalize_timestamp(None)
            self._save_unlocked()
            return True

    def resolve_incidents(self, incident_keys: list[str], verification_id: str) -> list[str]:
        """
        Resolve all unresolved alerts matching any of the given incident keys.

        Called by the state machine when a clean verification pass follows
        a broken chain state.

        Parameters
        ----------
        incident_keys : list[str]
            Keys to resolve (e.g. ``["block-7-hash_mismatch"]``).
        verification_id : str
            The passing verification that resolved these incidents.

        Returns
        -------
        list[str]
            Alert IDs that were transitioned to ``resolved``.
        """
        resolved_ids: list[str] = []
        now = _normalize_timestamp(None)
        with self._lock:
            for alert_id, rec in self._index.items():
                if rec.get("status") in ("active", "acknowledged"):
                    if rec.get("incident_key", "") in incident_keys:
                        rec["status"] = "resolved"
                        rec["resolved_at"] = now
                        rec["acknowledged"] = True  # legacy compat
                        rec["resolved_by_verification"] = verification_id
                        resolved_ids.append(alert_id)
            if resolved_ids:
                self._save_unlocked()
        return resolved_ids

    def resolve_all_unresolved(self, verification_id: str) -> list[str]:
        """
        Resolve every unresolved alert (used on a clean pass after broken state).

        Parameters
        ----------
        verification_id : str
            The passing verification ID.

        Returns
        -------
        list[str]
            Alert IDs resolved.
        """
        all_keys = list({
            rec.get("incident_key", "")
            for rec in self._index.values()
            if rec.get("status") in ("active", "acknowledged")
        })
        return self.resolve_incidents(all_keys, verification_id)

    # ── Read operations ────────────────────────────────────────────────

    def get_active_alerts(self) -> list[dict]:
        """Return alerts with status ``active`` or ``acknowledged``, newest first."""
        with self._lock:
            results = [
                r for r in self._index.values()
                if r.get("status") in ("active", "acknowledged")
            ]
        return sorted(results, key=lambda r: r.get("created_at", ""), reverse=True)

    def get_resolved_alerts(self) -> list[dict]:
        """Return alerts with status ``resolved``, newest first."""
        with self._lock:
            results = [
                r for r in self._index.values()
                if r.get("status") == "resolved"
            ]
        return sorted(results, key=lambda r: r.get("resolved_at", ""), reverse=True)

    def get_all_alerts(self, status: str | None = None) -> list[dict]:
        """
        Return all alerts, optionally filtered by status.

        Parameters
        ----------
        status : str | None
            If provided, must be one of ``"active"``, ``"acknowledged"``,
            ``"resolved"``, or ``"all"``. ``None`` / ``"all"`` returns
            everything.

        Returns
        -------
        list[dict]
            Alerts newest first.
        """
        with self._lock:
            all_recs = list(self._index.values())

        if status and status != "all":
            if status in ("active", "acknowledged", "resolved"):
                all_recs = [r for r in all_recs if r.get("status") == status]
            elif status == "unresolved":
                all_recs = [r for r in all_recs if r.get("status") in ("active", "acknowledged")]

        return sorted(all_recs, key=lambda r: r.get("created_at", ""), reverse=True)

    def get_alert_by_id(self, alert_id: str) -> dict | None:
        """Return a single alert by ID."""
        with self._lock:
            rec = self._index.get(alert_id)
            return dict(rec) if rec else None

    def get_counts(self) -> dict[str, int]:
        """
        Return alert counts by lifecycle status.

        Returns
        -------
        dict
            ``{active, acknowledged, resolved, total}``
        """
        with self._lock:
            active = sum(1 for r in self._index.values() if r.get("status") == "active")
            acknowledged = sum(1 for r in self._index.values() if r.get("status") == "acknowledged")
            resolved = sum(1 for r in self._index.values() if r.get("status") == "resolved")
        return {
            "active": active,
            "acknowledged": acknowledged,
            "resolved": resolved,
            "total": active + acknowledged + resolved,
        }

    def get_last_resolved(self) -> dict | None:
        """Return the most recently resolved alert, or None."""
        with self._lock:
            return max((r for r in self._index.values() if r.get("status") == "resolved"), key=lambda r: r.get("resolved_at", ""), default=None)

    def get_unresolved_incident_keys(self) -> list[str]:
        """Return incident_key values for all unresolved alerts."""
        with self._lock:
            return [
                rec.get("incident_key", "")
                for rec in self._index.values()
                if rec.get("status") in ("active", "acknowledged")
            ]

    # ── Internal helpers ───────────────────────────────────────────────

    def _find_unresolved_by_key_unlocked(self, incident_key: str) -> dict | None:
        """Find first unresolved alert matching incident_key. Caller holds lock."""
        return next((rec for rec in self._index.values() if rec.get("incident_key") == incident_key and rec.get("status") in ("active", "acknowledged")), None)
