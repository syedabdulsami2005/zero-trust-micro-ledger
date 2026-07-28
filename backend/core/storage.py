"""
Append-only JSONL storage for the micro-ledger.

Handles all file I/O for ledger blocks, runtime state, and alerts.
Enforces the TRD storage rules:
  - One block per line (JSONL)
  - UTF-8 encoding
  - No in-place updates after append (Rule 8)
  - Line-by-line streaming reads (memory constraint)
  - Robust exception handling for filesystem errors (Rule 3)
"""

import json
import os
import shutil
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator




class StorageError(Exception):
    """Raised on unrecoverable storage I/O failures."""


class Storage:
    """
    Append-only JSONL storage backend.

    Parameters
    ----------
    data_dir : str | Path
        Root data directory (e.g. ``c:/mini project-2/data``).
    """

    def __init__(self, data_dir: str | Path) -> None:
        self.data_dir = Path(data_dir)
        self.ledger_dir = self.data_dir / "ledger" / "current"
        self.archive_dir = self.data_dir / "ledger" / "archive"
        self.checkpoint_dir = self.data_dir / "ledger" / "checkpoints"
        self.watched_dir = self.data_dir / "watched"
        self.runtime_dir = self.data_dir / "runtime"
        self.audit_dir = self.data_dir / "audit"

        # Canonical file paths
        self.ledger_file = self.ledger_dir / "ledger.jsonl"
        self.state_file = self.ledger_dir / "state.json"
        self.alerts_file = self.ledger_dir / "alerts.jsonl"
        self.audit_file = self.audit_dir / "user_activity.jsonl"

    # ── Directory management ───────────────────────────────────────────

    def ensure_directories(self) -> None:
        """Create all required directories if they do not exist."""
        for d in (
            self.ledger_dir,
            self.archive_dir,
            self.checkpoint_dir,
            self.watched_dir,
            self.runtime_dir,
            self.audit_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    # ── Block I/O ──────────────────────────────────────────────────────

    def append_jsonl(self, file_path: Path, record: dict, error_prefix: str) -> None:
        """Helper to append a single dict as one JSONL line with flush/fsync."""
        try:
            line = json.dumps(
                record,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            with open(file_path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        except OSError as exc:
            raise StorageError(f"{error_prefix}: {exc}") from exc

    def append_block(self, block: dict) -> None:
        """
        Append a single block as one JSON line to the ledger file.

        Uses write → flush → fsync to minimise data-loss risk.

        Raises
        ------
        StorageError
            If the write fails for any reason.
        """
        self.append_jsonl(self.ledger_file, block, "Failed to append block")

    def stream_blocks(self) -> Generator[dict, None, None]:
        """
        Yield blocks one at a time by streaming the ledger file.

        This is the memory-safe read path required by the TRD (verifier
        must stream line-by-line, < 64 MB preferred).

        Yields
        ------
        dict
            Parsed block dict for each valid JSONL line.

        Raises
        ------
        StorageError
            If the file cannot be opened or a line is malformed JSON.
        """
        if not self.ledger_file.exists():
            return

        try:
            with open(self.ledger_file, "r", encoding="utf-8") as fh:
                for line_no, raw_line in enumerate(fh, start=1):
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    try:
                        yield json.loads(stripped)
                    except json.JSONDecodeError as exc:
                        raise StorageError(
                            f"Malformed JSON on line {line_no}: {exc}"
                        ) from exc
        except OSError as exc:
            raise StorageError(f"Cannot read ledger file: {exc}") from exc

    def read_all_blocks(self) -> list[dict]:
        """
        Read every block into a list.

        For small ledgers this is convenient; for large ledgers prefer
        :meth:`stream_blocks`.
        """
        return list(self.stream_blocks())

    def read_block_by_index(self, index: int) -> dict | None:
        """Scan the ledger for a block with the given ``block_index``."""
        return next((b for b in self.stream_blocks() if b.get("block_index") == index), None)

    def get_block_count(self) -> int:
        """Return the number of blocks without loading all into memory."""
        return sum(1 for _ in self.stream_blocks())

    def get_last_block(self) -> dict | None:
        """Read only the last block from the ledger file."""
        blocks = self.read_all_blocks()
        return blocks[-1] if blocks else None

    # ── State I/O ──────────────────────────────────────────────────────

    def save_state(self, state: dict) -> None:
        """
        Write the runtime state file atomically, merging with existing state.

        Writes to a temporary file first, then renames for crash safety.
        """
        existing = self.load_state() or {}
        existing.update(state)
        tmp_path = self.state_file.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(existing, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            # Atomic rename (on Windows this replaces the target, retry if briefly locked)
            import time
            for attempt in range(5):
                try:
                    tmp_path.replace(self.state_file)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        except OSError as exc:
            raise StorageError(f"Failed to save state: {exc}") from exc

    def load_state(self) -> dict | None:
        """
        Load the runtime state file.  Returns ``None`` if it does not
        exist.
        """
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Failed to load state: {exc}") from exc

    # ── Alerts I/O ─────────────────────────────────────────────────────

    def append_alert(self, alert: dict) -> None:
        """Append a single alert record to the alerts JSONL file."""
        self.append_jsonl(self.alerts_file, alert, "Failed to append alert")

    def read_alerts(self) -> list[dict]:
        """Read all alerts from the alerts file."""
        if not self.alerts_file.exists():
            return []
        alerts = []
        try:
            with open(self.alerts_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped:
                        alerts.append(json.loads(stripped))
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Failed to read alerts: {exc}") from exc
        return alerts

    # ── Checkpoints & Recovery ─────────────────────────────────────────

    def _set_readonly(self, path: Path, readonly: bool) -> None:
        """Helper to toggle OS-level read-only file protection."""
        if not path.exists():
            return
        try:
            if readonly:
                os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
                if os.name == "nt":
                    subprocess.run(["attrib", "+r", str(path)], check=False, capture_output=True)
            else:
                if os.name == "nt":
                    subprocess.run(["attrib", "-r", str(path)], check=False, capture_output=True)
                os.chmod(path, stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IROTH)
        except Exception:
            pass

    def create_checkpoint(self, verification_id: str | None = None) -> Path | None:
        """
        Create a read-only, tamper-protected backup checkpoint of the current ledger.

        Uses smart deduplication: if `ledger_backup_latest.jsonl` already matches the
        current active ledger exactly (same block count and last block hash), no new duplicate
        files are created.
        """
        if not self.ledger_file.exists():
            return None

        self.ensure_directories()
        blocks = self.read_all_blocks()
        if not blocks:
            return None

        # Verify basic integrity before checkpointing
        if blocks[0].get("block_index") != 0:
            return None

        # Preserve initial baseline snapshot if not already present
        initial_path = self.checkpoint_dir / "ledger_backup_initial.jsonl"
        if not initial_path.exists():
            self._set_readonly(initial_path, readonly=False)
            try:
                shutil.copy2(self.ledger_file, initial_path)
                self._set_readonly(initial_path, readonly=True)
            except OSError:
                pass

        # Clean up any legacy per-block checkpoint files (e.g. ledger_backup_blocks-*.jsonl)
        for old_snap in self.checkpoint_dir.glob("ledger_backup_blocks-*.jsonl"):
            try:
                self._set_readonly(old_snap, readonly=False)
                old_snap.unlink(missing_ok=True)
            except OSError:
                pass

        latest_path = self.checkpoint_dir / "ledger_backup_latest.jsonl"
        
        # Smart Deduplication: check if existing latest_path has exact same size & last block
        if latest_path.exists():
            try:
                if latest_path.stat().st_size == self.ledger_file.stat().st_size:
                    with open(latest_path, "r", encoding="utf-8") as fh:
                        lines = [line.strip() for line in fh if line.strip()]
                    if lines and len(lines) == len(blocks):
                        last_backup_block = json.loads(lines[-1])
                        last_active_block = blocks[-1]
                        if (
                            last_backup_block.get("block_index") == last_active_block.get("block_index")
                            and last_backup_block.get("current_hash") == last_active_block.get("current_hash")
                        ):
                            # Completely identical! Skip creating duplicate checkpoints.
                            return latest_path
            except Exception:
                pass

        # Unlock if existing so we can update the latest clean checkpoint
        self._set_readonly(latest_path, readonly=False)
        try:
            shutil.copy2(self.ledger_file, latest_path)
            self._set_readonly(latest_path, readonly=True)
        except OSError as exc:
            raise StorageError(f"Failed to create latest checkpoint: {exc}") from exc

        return latest_path

    def restore_from_checkpoint(self, checkpoint_filename: str | None = None) -> dict:
        """
        Restore the active ledger from an immutable backup checkpoint.

        If `checkpoint_filename` is not specified, restores from `ledger_backup_latest.jsonl`.
        """
        self.ensure_directories()
        if checkpoint_filename:
            source_path = self.checkpoint_dir / checkpoint_filename
        else:
            source_path = self.checkpoint_dir / "ledger_backup_latest.jsonl"

        if not source_path.exists():
            # Fallback: check if any checkpoint exists and take the most recently modified
            checkpoints = sorted(self.checkpoint_dir.glob("ledger_backup_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not checkpoints:
                raise StorageError("No backup checkpoints found to restore from.")
            source_path = checkpoints[0]

        # Verify checkpoint validity before overwriting live ledger
        try:
            with open(source_path, "r", encoding="utf-8") as fh:
                lines = [line.strip() for line in fh if line.strip()]
            if not lines:
                raise StorageError(f"Checkpoint file {source_path.name} is empty.")
            first_block = json.loads(lines[0])
            if first_block.get("block_index") != 0:
                raise StorageError(f"Checkpoint {source_path.name} is malformed (no genesis block).")
        except Exception as exc:
            raise StorageError(f"Cannot restore from invalid checkpoint {source_path.name}: {exc}") from exc

        # Unlock target ledger file if read-only, overwrite cleanly with checkpoint, and sync
        self._set_readonly(self.ledger_file, readonly=False)
        try:
            with open(self.ledger_file, "w", encoding="utf-8") as out_fh:
                for line in lines:
                    out_fh.write(line + "\n")
                out_fh.flush()
                os.fsync(out_fh.fileno())
        except OSError as exc:
            raise StorageError(f"Failed to restore ledger from checkpoint: {exc}") from exc

        return {
            "success": True,
            "restored_from": source_path.name,
            "blocks_restored": len(lines),
        }

    def list_checkpoints(self) -> list[dict]:
        """Return a list of all available backup checkpoints with metadata."""
        if not self.checkpoint_dir.exists():
            return []
        
        results = []
        for path in sorted(self.checkpoint_dir.glob("ledger_backup_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                st = path.stat()
                results.append({
                    "filename": path.name,
                    "size_bytes": st.st_size,
                    "updated_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                    "read_only": not bool(st.st_mode & stat.S_IWRITE),
                })
            except OSError:
                continue
        return results

    # ── User Activity Audit I/O ────────────────────────────────────────

    def append_user_activity(self, entry: dict) -> None:
        """Append a single user action or session lifecycle record to user_activity.jsonl."""
        self.ensure_directories()
        self.append_jsonl(self.audit_file, entry, "Failed to append user activity")

    def read_user_activity(self, session_id: str | None = None) -> list[dict]:
        """Read all user activity and session logs, optionally filtered by session_id."""
        if not self.audit_file.exists():
            return []
        entries = []
        try:
            with open(self.audit_file, "r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped:
                        record = json.loads(stripped)
                        if session_id is None or record.get("session_id") == session_id:
                            entries.append(record)
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Failed to read user activity: {exc}") from exc
        return entries
