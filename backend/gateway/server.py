"""
Local Communication Gateway server.

Wraps Python's stdlib ``http.server.HTTPServer`` in a daemon thread,
bound exclusively to ``127.0.0.1``.  Exposes the same start/stop/is_running
lifecycle as ``VerificationDaemon`` for consistency.

Design notes:
  - The handler class attribute ``context`` is injected via a dynamic
    subclass so each request handler has access to the shared backend
    objects without module-level globals (Rule 5).
  - ``allow_reuse_address = True`` prevents "address already in use"
    errors during rapid test teardown / restart.
"""

from __future__ import annotations

import logging
import threading
from http.server import HTTPServer

from backend.gateway.context import GatewayContext
from backend.gateway.handlers import LedgerRequestHandler

logger = logging.getLogger(__name__)

# Default binding
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8765


class GatewayServer:
    """
    Local HTTP gateway server.

    Parameters
    ----------
    context : GatewayContext
        Shared backend references for the request handler.
    host : str
        Interface to bind to (default ``127.0.0.1``).
    port : int
        TCP port (default ``8765``).
    """

    def __init__(
        self,
        context: GatewayContext,
        host: str = _DEFAULT_HOST,
        port: int = _DEFAULT_PORT,
    ) -> None:
        self._context = context
        self._host = host
        self._port = port

        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────

    def start(self) -> None:
        """
        Start the HTTP server in a background daemon thread.

        Idempotent — a second call while running is a no-op.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return

            # Build a handler subclass with the context baked in
            ctx = self._context

            class _BoundHandler(LedgerRequestHandler):
                context = ctx

            server = HTTPServer((self._host, self._port), _BoundHandler)
            server.allow_reuse_address = True

            self._server = server
            self._thread = threading.Thread(
                target=server.serve_forever,
                name="gateway-server",
                daemon=True,
            )
            self._thread.start()
            logger.info(
                "Gateway server started on http://%s:%d", self._host, self._port
            )

    def stop(self, timeout: float = 5.0) -> None:
        """
        Shut down the HTTP server and wait for the thread to exit.

        Parameters
        ----------
        timeout : float
            Maximum seconds to wait for the thread to join.
        """
        with self._lock:
            if not (self._thread is not None and self._thread.is_alive()):
                return
            server_to_stop = self._server
            thread_to_join = self._thread

        if server_to_stop is not None:
            server_to_stop.shutdown()

        if thread_to_join is not None:
            thread_to_join.join(timeout=timeout)

        with self._lock:
            self._server = None
            self._thread = None
            logger.info("Gateway server stopped")

    def is_running(self) -> bool:
        """Return ``True`` if the server thread is active."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    @property
    def host(self) -> str:
        """Bound hostname."""
        return self._host

    @property
    def port(self) -> int:
        """Bound port number."""
        return self._port

    @property
    def base_url(self) -> str:
        """Convenience base URL for this server."""
        return f"http://{self._host}:{self._port}"
