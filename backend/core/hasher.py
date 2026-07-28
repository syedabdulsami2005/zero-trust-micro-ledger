"""
Canonical serialization and SHA-256 hashing.

Implements the TRD hashing contract:
  current_hash = SHA256(P || S)
where
  P = previous_hash (hex string)
  S = canonical JSON serialization of the block *excluding* current_hash

Canonical serialization rules (TRD §Canonical Serialization Rule):
  1. UTF-8 encoding
  2. Normalised line endings (\\n)
  3. Predictable replacement for invalid byte sequences
  4. Sorted JSON keys
  5. Compact separators with no non-semantic whitespace
  6. Exclusion of current_hash from the preimage
  7. Exact preservation of null, numeric, and boolean values
"""

import hashlib
import json



def canonical_serialize(block: dict) -> str:
    """
    Serialise a block dict into its canonical JSON string, excluding
    ``current_hash``.

    The output is deterministic: identical logical content always
    produces the identical string, which in turn produces the same hash.

    Parameters
    ----------
    block : dict
        A complete or partial block dict.  The ``current_hash`` key, if
        present, is excluded from the serialised output.

    Returns
    -------
    str
        Compact, sorted-key JSON string.
    """
    # Shallow-copy so we don't mutate the caller's dict
    preimage = {k: v for k, v in block.items() if k != "current_hash"}

    return json.dumps(
        preimage,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,

    )





def compute_hash(previous_hash: str, serialized_block: str) -> str:
    """
    Compute the current block hash per the TRD hashing rule.

    ``current_hash = SHA256(P || S)``

    Parameters
    ----------
    previous_hash : str
        Hex-encoded SHA-256 hash of the previous block (64 hex chars),
        or the genesis null hash (64 zeros).
    serialized_block : str
        The canonical JSON serialisation of the block (excluding
        ``current_hash``).

    Returns
    -------
    str
        Lowercase hex-encoded SHA-256 digest (64 characters).
    """
    preimage = (previous_hash + serialized_block).encode("utf-8")
    return hashlib.sha256(preimage).hexdigest()


def hash_content(data: bytes) -> str:
    """
    Compute the SHA-256 hex digest of arbitrary bytes.

    Useful for snapshot hashing of monitored file contents.

    Parameters
    ----------
    data : bytes
        Raw bytes to hash.

    Returns
    -------
    str
        Lowercase hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(data).hexdigest()
