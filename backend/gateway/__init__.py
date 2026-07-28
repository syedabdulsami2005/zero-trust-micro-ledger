"""
Local Communication Gateway package.

Exposes a read-only local HTTP server bound to 127.0.0.1 that
serves backend state to the dashboard UI (Phase 4).
"""

from backend.gateway.server import GatewayServer

__all__ = ["GatewayServer"]
