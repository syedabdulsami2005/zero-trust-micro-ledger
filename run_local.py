"""
run_local.py — one-command local launcher for the MicroLedger system.

Starts:
  1. Python backend: LedgerEngine + VerificationDaemon + GatewayServer
  2. Opens the browser to the frontend (if already built or dev server is running)

Usage:
  py -3.13 run_local.py [--data-dir DATA_DIR] [--port PORT] [--interval SECONDS]

The data directory is created automatically if it does not exist.
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from backend.capture.watcher import SourceWatcher
from backend.core.alert_store import AlertStore
from backend.core.ledger_engine import LedgerEngine
from backend.core.state_manager import StateManager
from backend.core.storage import Storage
from backend.core.verification_store import VerificationStore
from backend.daemon.daemon import VerificationDaemon
from backend.gateway.context import GatewayContext
from backend.gateway.server import GatewayServer


def parse_args():
    p = argparse.ArgumentParser(description="MicroLedger local launcher")
    p.add_argument("--data-dir",  default="data",  help="Data directory (default: data)")
    p.add_argument("--port",      type=int, default=8765, help="Gateway port (default: 8765)")
    p.add_argument("--interval",  type=float, default=30.0, help="Verification interval seconds (default: 30)")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("run_local")

    data_dir = Path(args.data_dir)
    logger.info("Starting MicroLedger — data dir: %s, port: %d", data_dir, args.port)

    # ── Bootstrap backend ─────────────────────────────────────────────
    storage = Storage(data_dir)
    storage.ensure_directories()

    engine = LedgerEngine(storage)
    engine.initialize()
    logger.info("Ledger engine initialised — %d blocks", engine.get_chain_length())

    # Alert store — mutable lifecycle index (separate from append-only JSONL)
    alert_store = AlertStore(storage.ledger_dir)
    state_manager = StateManager(storage, alert_store=alert_store)
    state_manager.load_from_disk()

    verification_store = VerificationStore(storage)

    daemon = VerificationDaemon(
        engine=engine,
        storage=storage,
        state_manager=state_manager,
        verification_store=verification_store,
        alert_store=alert_store,
        interval_seconds=args.interval,
    )
    daemon.start()
    logger.info("Verification daemon started (interval: %ss)", args.interval)

    # Startup reconciliation: if the chain is already healthy on boot but there are
    # unresolved alerts from a prior session, run a verification pass immediately so
    # the state machine can auto-resolve them and set active_alert_count to 0.
    if (state_manager.get_health_status() == "healthy"
            and alert_store.get_counts().get("active", 0) > 0):
        logger.info("Startup: chain is healthy but has stale active alerts — running reconciliation pass.")
        try:
            daemon.run_once()
        except Exception:
            logger.exception("Startup reconciliation pass failed")


    watcher = SourceWatcher(
        engine=engine,
        storage=storage,
        state_manager=state_manager,
        interval_seconds=10.0,
    )
    watcher.start()
    logger.info("Source watcher started (monitoring %d sources)", len(watcher._watched_paths))

    ctx = GatewayContext(
        engine=engine,
        storage=storage,
        state_manager=state_manager,
        verification_store=verification_store,
        daemon=daemon,
        alert_store=alert_store,
        watcher=watcher,
    )
    gateway = GatewayServer(ctx, port=args.port)
    gateway.start()
    logger.info("Gateway running at %s", gateway.base_url)

    # ── Graceful shutdown ─────────────────────────────────────────────
    def shutdown(sig, frame):
        logger.info("Shutting down…")
        gateway.stop()
        watcher.stop()
        daemon.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print(f"\n{'='*55}")
    print(f"  MicroLedger SOC — Gateway: {gateway.base_url}")
    print(f"  Chain length : {engine.get_chain_length()} blocks")
    print(f"  Health       : {state_manager.get_health_status()}")
    print(f"  Verify every : {args.interval}s")
    print(f"{'='*55}")
    print("  Start the frontend: cd frontend && npm run dev")
    print(f"  Dashboard URL:      http://localhost:5173")
    print(f"{'='*55}\n")
    print("  Press Ctrl+C to stop.\n")

    # Keep main thread alive
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
