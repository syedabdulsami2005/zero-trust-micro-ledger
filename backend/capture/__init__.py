"""
Capture layer for MicroLedger SOC.

Observes configured source files, captures initial snapshots and changes,
and normalizes them into structured events appended to the core ledger.
"""

from backend.capture.watcher import SourceWatcher

__all__ = ["SourceWatcher"]
