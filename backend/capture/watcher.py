"""
Source file watcher and snapshot generator.

Monitors configured local files for creation, modification, and deletion.
Generates deterministic normalized events with rich change classification
and appends them to the ledger via the single write path (LedgerEngine.append_event).

Enforces:
  - Rule 1: Zero reliance on external dependencies (pure Python pathlib/hashlib).
  - Rule 2: Halts appends immediately if LedgerEngine is frozen.
  - Rule 3: Robust exception handling (never crashes on I/O or permission errors).
  - Rule 5: Single writer (forwards all events to LedgerEngine).
  - Rule 7: Captures source read failures into structured state.

File change classification:
  - file_created     : file appeared for the first time (never seen before).
  - file_deleted     : previously tracked file is now missing.
  - data_added       : file grew in size (content was appended).
  - data_deleted     : file shrank in size (content was removed).
  - content_modified : file content changed but size delta is ambiguous.
"""

import hashlib
import logging
import threading
import time
from pathlib import Path
from typing import Any

from backend.core.ledger_engine import LedgerEngine, LedgerFrozenError
from backend.core.normalizer import _normalize_timestamp
from backend.core.state_manager import StateManager
from backend.core.storage import Storage

logger = logging.getLogger(__name__)


def _classify_change(
    prev_size: int,
    new_size: int,
    is_first_seen: bool,
    file_existed: bool,
) -> tuple[str, str]:
    """
    Classify a file change event.

    Parameters
    ----------
    prev_size : int
        File size before the change (bytes). 0 if unknown.
    new_size : int
        Current file size (bytes).
    is_first_seen : bool
        True if this is the first time the file has been seen.
    file_existed : bool
        True if the file currently exists on disk.

    Returns
    -------
    tuple[str, str]
        (change_type, change_label) where change_type is the machine key
        and change_label is the human-readable description.
    """
    if not file_existed:
        return "file_deleted", "File was deleted"
    if is_first_seen:
        return "file_created", "New file captured"
    if new_size > prev_size:
        return "data_added", "Data added to file"
    if new_size < prev_size:
        return "data_deleted", "Data removed from file"
    return "content_modified", "Content modified (same size)"


class SourceWatcher:
    """
    Periodic local file watcher and snapshot engine.

    Parameters
    ----------
    engine : LedgerEngine
        The core ledger engine used for appending event blocks.
    storage : Storage
        Storage instance to resolve default paths and read history.
    state_manager : StateManager
        Runtime state tracker.
    watched_paths : list[Path | str] | None
        List of files to monitor. If None, defaults to the standard
        ``data/watched/`` demo candidates.
    interval_seconds : float
        Polling interval in seconds between file scans (default 10.0).
    """

    def __init__(
        self,
        engine: LedgerEngine,
        storage: Storage,
        state_manager: StateManager,
        watched_paths: list[Path | str] | None = None,
        interval_seconds: float = 10.0,
    ) -> None:
        self._engine = engine
        self._storage = storage
        self._state_manager = state_manager
        self._interval = interval_seconds

        if watched_paths is None:
            self._watched_paths: list[Path] = [
                self._storage.watched_dir / "test_config.json",
                self._storage.watched_dir / "test_log.log",
                self._storage.watched_dir / "firmware_state.txt",
            ]
        else:
            self._watched_paths = [Path(p) for p in watched_paths]

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # In-memory tracking: canonical path string -> last known sha256
        self._file_hashes: dict[str, str] = {}
        # In-memory tracking: canonical path string -> last known size (bytes)
        self._file_sizes: dict[str, int] = {}
        # In-memory status for API reporting: canonical path -> status dict
        self._source_statuses: dict[str, dict[str, Any]] = {}

    def _determine_source_type(self, path: Path) -> str:
        """Map filename extension to a valid TRD ``source_type``."""
        ext = path.suffix.lower()
        if ext in (".json", ".conf", ".ini", ".cfg", ".yaml", ".yml"):
            return "config_file"
        elif ext in (".log", ".txt", ".out"):
            return "log_file"
        elif ext in (".bin", ".exe", ".dll", ".so"):
            return "binary_file"
        return "system"

    def _load_existing_snapshots_from_ledger(self) -> None:
        """Scan historical ledger blocks to initialize known file hashes and sizes."""
        try:
            for block in self._storage.stream_blocks():
                src_path = block.get("source_path")
                if not src_path or block.get("event_type") == "genesis":
                    continue
                log_data = block.get("log_data")
                if isinstance(log_data, dict):
                    if log_data.get("snapshot_sha256"):
                        self._file_hashes[src_path] = log_data["snapshot_sha256"]
                    # Restore size from metadata if available
                    meta = log_data.get("metadata", {})
                    if isinstance(meta, dict) and meta.get("size_bytes"):
                        self._file_sizes[src_path] = meta["size_bytes"]
        except Exception:
            logger.exception(
                "Failed to scan historical ledger snapshots during watcher initialization"
            )

    def start(self) -> None:
        """Start the background file watcher thread after taking initial snapshots."""
        with self._lock:
            if self._is_running_unlocked():
                return

            self._load_existing_snapshots_from_ledger()
            # Perform initial synchronous scan on startup
            self._scan_once_unlocked()

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="source-watcher-daemon",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the background watcher thread."""
        with self._lock:
            if not self._is_running_unlocked():
                return
            self._stop_event.set()
            thread_to_join = self._thread

        if thread_to_join is not None:
            thread_to_join.join(timeout=timeout)

        with self._lock:
            self._thread = None

    def is_running(self) -> bool:
        """Return True if the background watcher loop is running."""
        with self._lock:
            return self._is_running_unlocked()

    def _is_running_unlocked(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _loop(self) -> None:
        """Main background polling loop."""
        while not self._stop_event.is_set():
            try:
                self.scan_once()
            except Exception:
                logger.exception("Source watcher loop encountered an unexpected error")
            self._stop_event.wait(timeout=self._interval)

    def scan_once(self) -> None:
        """Perform a single check across all configured watched paths."""
        with self._lock:
            self._scan_once_unlocked()

    def _scan_once_unlocked(self) -> None:
        """Scan watched files while holding ``_lock``."""
        if self._engine.is_frozen() or self._state_manager.get_state().get("frozen", False):
            logger.warning("Ledger is frozen; skipping watcher scan until unfreeze")
            return

        now_utc = _normalize_timestamp(None)

        for path in self._watched_paths:
            canonical_path = str(path.resolve() if path.exists() else path)
            source_type = self._determine_source_type(path)
            source_identifier = path.name

            # Initialize status tracking entry if not present
            if canonical_path not in self._source_statuses:
                self._source_statuses[canonical_path] = {
                    "source_path": canonical_path,
                    "source_type": source_type,
                    "source_identifier": source_identifier,
                    "status": "checking",
                    "last_checked_utc": now_utc,
                    "last_snapshot_sha256": None,
                    "size_bytes": 0,
                    "error": None,
                }

            status_entry = self._source_statuses[canonical_path]
            status_entry["last_checked_utc"] = now_utc

            if not path.exists():
                status_entry["status"] = "missing"
                status_entry["error"] = "File not found on disk"
                # If we previously knew about this file, record deletion event
                if canonical_path in self._file_hashes:
                    change_type, change_label = _classify_change(
                        prev_size=self._file_sizes.get(canonical_path, 0),
                        new_size=0,
                        is_first_seen=False,
                        file_existed=False,
                    )
                    try:
                        self._engine.append_event({
                            "event_type": "file_deleted",
                            "source_type": source_type,
                            "source_path": canonical_path,
                            "source_identifier": source_identifier,
                            "log_data": {
                                "summary": f"Monitored file {source_identifier} was deleted or missing",
                                "change_type": change_type,
                                "change_label": change_label,
                                "raw_line": None,
                                "snapshot_sha256": None,
                                "previous_sha256": self._file_hashes[canonical_path],
                                "metadata": {
                                    "actor": "source_watcher",
                                    "status": "deleted",
                                    "previous_size_bytes": self._file_sizes.get(canonical_path, 0),
                                    "previous_sha256": self._file_hashes[canonical_path],
                                },
                            },
                        })
                        del self._file_hashes[canonical_path]
                        if canonical_path in self._file_sizes:
                            del self._file_sizes[canonical_path]
                    except LedgerFrozenError:
                        logger.warning(
                            "Ledger frozen while trying to record deletion of %s", canonical_path
                        )
                    except Exception:
                        logger.exception(
                            "Failed to record file_deleted event for %s", canonical_path
                        )
                continue

            # Read file and compute hash safely per Rule 3
            try:
                content = path.read_bytes()
                new_size = len(content)
                sha256 = hashlib.sha256(content).hexdigest()
            except OSError as exc:
                status_entry["status"] = "error"
                status_entry["error"] = f"Read error: {exc}"
                logger.error("Failed reading watched file %s: %s", canonical_path, exc)
                continue

            status_entry["size_bytes"] = new_size
            status_entry["last_snapshot_sha256"] = sha256
            status_entry["error"] = None

            previous_sha256 = self._file_hashes.get(canonical_path)
            previous_size = self._file_sizes.get(canonical_path, 0)

            if previous_sha256 is None:
                # First time capturing this file → classify as file_created
                change_type, change_label = _classify_change(
                    prev_size=0,
                    new_size=new_size,
                    is_first_seen=True,
                    file_existed=True,
                )
                # For backwards compat, keep the existing event_type conventions
                if source_type == "config_file":
                    event_type = "config_changed"
                elif source_type == "log_file":
                    event_type = "log_entry"
                else:
                    event_type = "file_created"

                try:
                    self._engine.append_event({
                        "event_type": event_type,
                        "source_type": source_type,
                        "source_path": canonical_path,
                        "source_identifier": source_identifier,
                        "log_data": {
                            "summary": f"Initial snapshot captured for {source_identifier}",
                            "change_type": change_type,
                            "change_label": change_label,
                            "raw_line": None,
                            "snapshot_sha256": sha256,
                            "previous_sha256": None,
                            "metadata": {
                                "actor": "source_watcher",
                                "encoding": "utf-8",
                                "size_bytes": new_size,
                                "initial_snapshot": True,
                            },
                        },
                    })
                    self._file_hashes[canonical_path] = sha256
                    self._file_sizes[canonical_path] = new_size
                    status_entry["status"] = "monitored"
                    logger.info(
                        "Captured initial snapshot for %s (%s)", source_identifier, sha256[:8]
                    )
                except LedgerFrozenError:
                    status_entry["status"] = "frozen"
                except Exception as exc:
                    status_entry["status"] = "error"
                    status_entry["error"] = str(exc)
                    logger.exception(
                        "Failed appending initial snapshot for %s", canonical_path
                    )

            elif sha256 != previous_sha256:
                # File content has changed since previous snapshot
                change_type, change_label = _classify_change(
                    prev_size=previous_size,
                    new_size=new_size,
                    is_first_seen=False,
                    file_existed=True,
                )

                # event_type: keep existing conventions for backward compat
                if source_type == "config_file":
                    event_type = "config_changed"
                elif source_type == "log_file":
                    event_type = "log_entry"
                else:
                    event_type = "file_modified"

                try:
                    self._engine.append_event({
                        "event_type": event_type,
                        "source_type": source_type,
                        "source_path": canonical_path,
                        "source_identifier": source_identifier,
                        "log_data": {
                            "summary": (
                                f"{change_label}: {source_identifier}"
                            ),
                            "change_type": change_type,
                            "change_label": change_label,
                            "raw_line": None,
                            "snapshot_sha256": sha256,
                            "previous_sha256": previous_sha256,
                            "metadata": {
                                "actor": "source_watcher",
                                "encoding": "utf-8",
                                "size_bytes": new_size,
                                "previous_size_bytes": previous_size,
                                "size_delta_bytes": new_size - previous_size,
                                "previous_sha256": previous_sha256,
                            },
                        },
                    })
                    self._file_hashes[canonical_path] = sha256
                    self._file_sizes[canonical_path] = new_size
                    status_entry["status"] = "modified"
                    logger.info(
                        "Captured %s event for %s (%s → %s)",
                        change_type,
                        source_identifier,
                        previous_sha256[:8],
                        sha256[:8],
                    )
                except LedgerFrozenError:
                    status_entry["status"] = "frozen"
                except Exception as exc:
                    status_entry["status"] = "error"
                    status_entry["error"] = str(exc)
                    logger.exception(
                        "Failed appending modification event for %s", canonical_path
                    )
            else:
                status_entry["status"] = "monitored"

    def get_monitored_sources(self) -> list[dict[str, Any]]:
        """Return current status of all configured watched files for API queries."""
        with self._lock:
            return list(self._source_statuses.values())
