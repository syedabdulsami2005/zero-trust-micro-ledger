"""
Sequential ledger append engine.

Manages the single write path for appending blocks to the micro-ledger.
Enforces:
  - Rule 2: Freeze appends immediately on verification failure
  - Rule 5: Single writer, controlled readers
  - Rule 8: Historical records are append-only (no update / delete)
"""

import threading


from backend.core.block import create_block, create_genesis_block
from backend.core.normalizer import normalize_event, _normalize_timestamp
from backend.core.storage import Storage, StorageError


class LedgerFrozenError(Exception):
    """Raised when an append is attempted on a frozen ledger."""


class LedgerEngine:
    """
    Core ledger append engine.

    This class owns the single write path.  All event ingestion flows
    through :meth:`append_event`, which enforces chain integrity and
    freeze discipline.

    Parameters
    ----------
    storage : Storage
        The storage backend to read from and write to.
    """

    def __init__(self, storage: Storage) -> None:
        self._storage = storage
        self._lock = threading.Lock()
        self._frozen = False
        self._last_block: dict | None = None
        self._chain_length: int = 0

    # ── Initialisation ─────────────────────────────────────────────────

    def initialize(self) -> dict:
        """
        Initialise the ledger.

        If the ledger file is empty, creates and persists the genesis
        block.  Otherwise, loads the last block from disk so the engine
        knows where to continue appending.

        Returns
        -------
        dict
            The genesis block (if newly created) or the last existing
            block.
        """
        with self._lock:
            self._storage.ensure_directories()

            existing_count = self._storage.get_block_count()

            if existing_count == 0:
                # Fresh ledger — create genesis
                genesis = create_genesis_block()
                self._storage.append_block(genesis)
                self._last_block = genesis
                self._chain_length = 1
                self._save_state()
                return genesis

            # Existing ledger — reload tail state
            last_block = self._storage.get_last_block()
            if last_block is None:
                raise StorageError("Ledger reported existing blocks but last block could not be read.")
            self._last_block = last_block
            self._chain_length = existing_count

            # Restore frozen state if previously saved
            saved_state = self._storage.load_state()
            if saved_state and saved_state.get("frozen", False):
                self._frozen = True

            return last_block

    # ── Append ─────────────────────────────────────────────────────────

    def append_event(self, raw_event: dict) -> dict:
        """
        Normalise a raw event, create a block, and append it.

        This is the **only** write path into the ledger.

        Parameters
        ----------
        raw_event : dict
            Raw event data (must contain ``event_type``, ``source_type``,
            ``source_path`` at minimum).

        Returns
        -------
        dict
            The newly appended block.

        Raises
        ------
        LedgerFrozenError
            If the ledger is frozen (verification failure detected).
        """
        with self._lock:
            if self._frozen:
                raise LedgerFrozenError(
                    "Ledger is frozen due to integrity failure. "
                    "Resolve the issue and call unfreeze() before appending."
                )

            if self._last_block is None:
                raise RuntimeError(
                    "LedgerEngine not initialised. Call initialize() first."
                )

            # Normalise the raw event
            normalized = normalize_event(raw_event)

            # Build the next block
            next_index = self._chain_length
            previous_hash = self._last_block["current_hash"]
            new_block = create_block(next_index, normalized, previous_hash)

            # Persist
            self._storage.append_block(new_block)
            self._last_block = new_block
            self._chain_length += 1
            self._save_state()

            return new_block

    # ── Query ──────────────────────────────────────────────────────────

    def get_last_block(self) -> dict | None:
        """Return the most recently appended block, or ``None``."""
        return self._last_block

    def get_chain_length(self) -> int:
        """Return the total number of blocks in the ledger."""
        return self._chain_length

    # ── Freeze / Unfreeze ──────────────────────────────────────────────

    def freeze(self) -> None:
        """
        Halt all append operations.

        Called by the verification daemon when chain corruption is
        detected.  Per Rule 2, no further blocks may be appended
        until the issue is resolved and :meth:`unfreeze` is called.
        """
        with self._lock:
            self._frozen = True
            self._save_state()

    def unfreeze(self) -> None:
        """
        Resume append operations after an integrity issue is resolved.

        Should only be called after manual investigation / recovery.
        """
        with self._lock:
            self._frozen = False
            self._save_state()

    def is_frozen(self) -> bool:
        """Return ``True`` if the ledger is currently frozen."""
        return self._frozen

    # ── Internal ───────────────────────────────────────────────────────

    def _save_state(self) -> None:
        """Persist current runtime state to the state file."""
        state = {
            "chain_length": self._chain_length,
            "last_block_index": (
                self._last_block["block_index"] if self._last_block else None
            ),
            "last_block_hash": (
                self._last_block["current_hash"] if self._last_block else None
            ),
            "frozen": self._frozen,
            "updated_utc": _normalize_timestamp(None),
        }
        self._storage.save_state(state)
