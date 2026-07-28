"""
Verification history persistence.

Appends verification run results to a JSONL file so they survive
process restarts.  Reads support a configurable limit to avoid
loading the entire history into memory.
"""

import json
from collections import deque
from pathlib import Path

from backend.core.storage import Storage, StorageError
from backend.core.verifier import VerificationResult


class VerificationStore:
    """
    Append-only store for verification run results.

    Parameters
    ----------
    storage : Storage
        Storage backend (used for directory paths).
    """

    def __init__(self, storage: Storage) -> None:
        self._storage = storage
        self._file: Path = storage.ledger_dir / "verifications.jsonl"

    def save_result(self, result: VerificationResult) -> None:
        """
        Append a verification result as one JSON line.

        Parameters
        ----------
        result : VerificationResult
            The result to persist.

        Raises
        ------
        StorageError
            If the write fails.
        """
        self._storage.append_jsonl(
            self._file, result.to_dict(), "Failed to save verification result"
        )

    def read_history(self, limit: int = 50) -> list[dict]:
        """
        Read verification history, returning the most recent results.

        Parameters
        ----------
        limit : int
            Maximum number of results to return (default 50).

        Returns
        -------
        list[dict]
            Most recent verification results, newest first.

        Raises
        ------
        StorageError
            If the file cannot be read or contains malformed JSON.
        """
        if limit <= 0 or not self._file.exists():
            return []

        try:
            with open(self._file, "r", encoding="utf-8") as fh:
                lines = deque((line.strip() for line in fh if line.strip()), maxlen=limit)
            return [json.loads(line) for line in reversed(lines)]
        except OSError as exc:
            raise StorageError(
                f"Cannot read verifications file: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise StorageError(
                f"Malformed verification record: {exc}"
            ) from exc
