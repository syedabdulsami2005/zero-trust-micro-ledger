"""
HTTP request handler for the Local Communication Gateway.

Routes all TRD endpoints and handles CORS, error responses, and
pagination.  Calls only backend objects supplied via GatewayContext —
no globals.

All handler methods:
  - Wrap backend calls in try/except → 500 JSON on unexpected errors
  - Set Content-Type: application/json on every response
  - Set Access-Control-Allow-Origin: * for Phase 4 React dev server

New endpoints added for alert lifecycle:
  POST /api/alerts/<id>/acknowledge  — transition active → acknowledged
  GET  /api/alerts?status=<s>        — filter by lifecycle status
  POST /api/exports                  — extended: format, filters, incident bundle
  GET  /api/events                   — extended: change_type, time_from, time_to, sort
"""

from __future__ import annotations

import json
import logging
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from backend.gateway.context import GatewayContext

logger = logging.getLogger(__name__)

# Compiled route patterns
_LEDGER_BLOCK_RE = re.compile(r"^/api/ledger/(\d+)$")
_ALERT_ACK_RE = re.compile(r"^/api/alerts/([\w-]+)/acknowledge$")


class LedgerRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for the micro-ledger gateway.

    The ``context`` class attribute is injected by ``GatewayServer``
    via a dynamically created subclass so every instance has access
    to the shared backend objects.
    """

    context: GatewayContext  # set by GatewayServer

    # ── Logging ───────────────────────────────────────────────────────

    def log_message(self, format: str, *args: object) -> None:  # noqa: D102, A002
        logger.debug("Gateway: %s", format % args)

    # ── Helpers ───────────────────────────────────────────────────────

    def _parse_url(self):
        """Return (path, query_dict) for the current request."""
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query, keep_blank_values=False)
        return parsed.path.rstrip("/"), qs

    def _int_param(self, qs: dict, name: str, default: int) -> int:
        """Extract an integer query parameter with a fallback default."""
        vals = qs.get(name, [])
        if vals:
            try:
                return max(0, int(vals[0]))
            except ValueError:
                pass
        return default

    def _str_param(self, qs: dict, name: str, default: str = "") -> str:
        """Extract a string query parameter with a fallback default."""
        vals = qs.get(name, [])
        return vals[0].strip() if vals else default

    def _send_json(self, data: object, status: int = 200) -> None:
        """Serialise *data* to JSON and write the full response."""
        body = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, content_type: str = "text/plain; charset=utf-8", status: int = 200) -> None:
        """Send a plain text or HTML response."""
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        """Send a structured JSON error response."""
        self._send_json({"error": message, "code": status}, status)

    def _read_body_json(self) -> dict:
        """Read and parse the request body as JSON. Returns {} on failure."""
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}

    def _drain_body(self) -> None:
        """Consume any unread request body to prevent TCP connection abort."""
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > 0:
            try:
                self.rfile.read(length)
            except Exception:
                pass

    # ── Dispatch ──────────────────────────────────────────────────────

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Handle pre-flight CORS requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        """Route GET requests."""
        path, qs = self._parse_url()

        routes = {
            "/api/health": self._handle_health,
            "/api/state": self._handle_state,
            "/api/files": self._handle_files,
            "/api/events": lambda: self._handle_events(qs),
            "/api/ledger": lambda: self._handle_ledger(qs),
            "/api/verification": lambda: self._handle_verification(qs),
            "/api/alerts": lambda: self._handle_alerts(qs),
            "/api/checkpoints": self._handle_checkpoints,
            "/api/audit/activity": lambda: self._handle_get_audit_activity(qs),
        }

        if path in routes:
            try:
                routes[path]()
            except Exception:
                logger.exception("Unhandled error in GET %s", path)
                self._error(500, "Internal server error")
            return

        # /api/ledger/<n>
        m = _LEDGER_BLOCK_RE.match(path)
        if m:
            try:
                self._handle_ledger_block(int(m.group(1)))
            except Exception:
                logger.exception("Unhandled error in GET %s", path)
                self._error(500, "Internal server error")
            return

        # POST-only routes hit via GET → 405
        post_only = {"/api/actions/run-verification", "/api/exports", "/api/actions/restore-checkpoint", "/api/auth/login", "/api/auth/logout"}
        if path in post_only or _ALERT_ACK_RE.match(path):
            self._error(405, "Method not allowed")
            return

        self._error(404, f"Unknown route: {path}")

    def do_POST(self) -> None:  # noqa: N802
        """Route POST requests."""
        path, _ = self._parse_url()

        # Alert acknowledge: POST /api/alerts/<id>/acknowledge
        m = _ALERT_ACK_RE.match(path)
        if m:
            try:
                self._handle_alert_acknowledge(m.group(1))
            except Exception:
                logger.exception("Unhandled error in POST %s", path)
                self._error(500, "Internal server error")
            return

        routes = {
            "/api/actions/run-verification": self._handle_run_verification,
            "/api/actions/restore-checkpoint": self._handle_restore_checkpoint,
            "/api/exports": self._handle_exports,
            "/api/auth/login": self._handle_auth_login,
            "/api/auth/logout": self._handle_auth_logout,
        }

        if path in routes:
            try:
                routes[path]()
            except Exception:
                logger.exception("Unhandled error in POST %s", path)
                self._error(500, "Internal server error")
            return

        # GET-only routes hit via POST → 405
        get_only = {
            "/api/health", "/api/state", "/api/files",
            "/api/events", "/api/ledger", "/api/verification", "/api/alerts", "/api/checkpoints", "/api/audit/activity",
        }
        if path in get_only or _LEDGER_BLOCK_RE.match(path):
            self._drain_body()
            self._error(405, "Method not allowed")
            return

        self._drain_body()
        self._error(404, f"Unknown route: {path}")

    # ── GET handlers ─────────────────────────────────────────────────

    def _handle_health(self) -> None:
        """`GET /api/health` — always 200."""
        from backend.core.normalizer import _normalize_timestamp
        self._send_json({
            "status": "ok",
            "daemon_running": self.context.daemon.is_running(),
            "timestamp_utc": _normalize_timestamp(None),
        })

    def _handle_state(self) -> None:
        """`GET /api/state` — full runtime state snapshot."""
        state = self.context.state_manager.get_state()
        state["chain_length"] = self.context.engine.get_chain_length()
        last_block = self.context.engine.get_last_block()
        if last_block:
            state["last_block_index"] = last_block.get("block_index")
            state["last_block_hash"] = last_block.get("current_hash")
        state["daemon_running"] = self.context.daemon.is_running()
        if self.context.watcher is not None:
            state["watcher_running"] = self.context.watcher.is_running()
        self._send_json(state)

    def _handle_files(self) -> None:
        """`GET /api/files` — unique source paths seen in the ledger plus live watched files."""
        seen: dict[str, dict] = {}
        if self.context.watcher is not None:
            for item in self.context.watcher.get_monitored_sources():
                p = item["source_path"]
                seen[p] = {
                    "source_path": p,
                    "source_type": item.get("source_type", "unknown"),
                    "source_identifier": item.get("source_identifier", ""),
                    "first_seen_utc": None,
                    "last_seen_utc": item.get("last_checked_utc"),
                    "event_count": 0,
                    "status": item.get("status", "monitored"),
                    "size_bytes": item.get("size_bytes", 0),
                    "last_snapshot_sha256": item.get("last_snapshot_sha256"),
                }

        for block in self.context.storage.stream_blocks():
            path = block.get("source_path")
            if not path or block.get("event_type") == "genesis":
                continue
            if path not in seen:
                seen[path] = {
                    "source_path": path,
                    "source_type": block.get("source_type", "unknown"),
                    "source_identifier": block.get("source_identifier", ""),
                    "first_seen_utc": block.get("timestamp_utc"),
                    "last_seen_utc": block.get("timestamp_utc"),
                    "event_count": 0,
                    "status": "monitored",
                }
            if seen[path].get("first_seen_utc") is None:
                seen[path]["first_seen_utc"] = block.get("timestamp_utc")
            seen[path]["last_seen_utc"] = block.get("timestamp_utc")
            seen[path]["event_count"] += 1

        self._send_json(list(seen.values()))

    def _filter_records(self, records: list[dict], time_from: str = "", time_to: str = "", file_name: str = "", change_type: str = "", from_index: int | None = None, to_index: int | None = None, ts_key: str = "timestamp_utc", is_block: bool = False, alert_id: str = "", incident_id: str = "") -> list[dict]:
        res = records
        if from_index is not None: res = [r for r in res if r.get("block_index", 0) >= from_index]
        if to_index is not None: res = [r for r in res if r.get("block_index", 0) <= to_index]
        if time_from: res = [r for r in res if (r.get(ts_key) or "") >= time_from]
        if time_to: res = [r for r in res if (r.get(ts_key) or "") <= time_to]
        if file_name: res = [r for r in res if file_name in (r.get("source_path") or "").lower() or file_name in (r.get("source_identifier") or "").lower()]
        if change_type: res = [r for r in res if ((r.get("log_data") or {}).get("change_type") if is_block else r.get("change_type")) == change_type]
        if alert_id:
            if is_block:
                alert = self.context.alert_store.get_alert_by_id(alert_id) if self.context.alert_store is not None else None
                if alert and alert.get("block_index") is not None:
                    res = [r for r in res if r.get("block_index") == alert.get("block_index")]
                else:
                    res = []
            else:
                res = [r for r in res if r.get("alert_id") == alert_id]
        if incident_id:
            if is_block:
                inc_alerts = [a for a in (self.context.alert_store.get_all_alerts() if self.context.alert_store is not None else []) if a.get("incident_key") == incident_id]
                block_idxs = {a.get("block_index") for a in inc_alerts if a.get("block_index") is not None}
                res = [r for r in res if r.get("block_index") in block_idxs]
            else:
                res = [r for r in res if r.get("incident_key") == incident_id]
        return res

    def _handle_events(self, qs: dict) -> None:
        """`GET /api/events` — recent events with optional filters."""
        limit = self._int_param(qs, "limit", 50)
        change_type_filter = self._str_param(qs, "change_type")
        file_name_filter = self._str_param(qs, "file_name").lower()
        time_from = self._str_param(qs, "time_from")
        time_to = self._str_param(qs, "time_to")
        sort_order = self._str_param(qs, "sort", "desc")

        blocks = self.context.storage.read_all_blocks()
        events = []
        for b in blocks:
            if b.get("event_type") == "genesis":
                continue
            log_data = b.get("log_data") or {}
            events.append({
                "event_id": b.get("event_id"),
                "event_type": b.get("event_type"),
                "change_type": log_data.get("change_type", ""),
                "change_label": log_data.get("change_label", ""),
                "source_type": b.get("source_type"),
                "source_path": b.get("source_path"),
                "source_identifier": b.get("source_identifier"),
                "timestamp_utc": b.get("timestamp_utc"),
                "block_index": b.get("block_index"),
                "ingest_sequence": b.get("ingest_sequence"),
                "previous_sha256": log_data.get("previous_sha256"),
                "current_sha256": log_data.get("snapshot_sha256"),
                "summary": log_data.get("summary", ""),
            })

        events = self._filter_records(events, time_from, time_to, file_name_filter, change_type_filter)
        events = list(reversed(events)) if sort_order in ("asc", "desc") else events

        if limit:
            events = events[:limit]
        self._send_json(events)

    def _handle_ledger(self, qs: dict) -> None:
        """`GET /api/ledger?limit=N&offset=M` — paginated block list."""
        limit = self._int_param(qs, "limit", 50)
        offset = self._int_param(qs, "offset", 0)

        all_blocks = self.context.storage.read_all_blocks()
        total = len(all_blocks)
        page = all_blocks[offset: offset + limit] if limit else all_blocks[offset:]

        self._send_json({
            "blocks": page,
            "total": total,
            "offset": offset,
            "limit": limit,
        })

    def _handle_ledger_block(self, block_index: int) -> None:
        """`GET /api/ledger/<n>` — single block by index."""
        block = self.context.storage.read_block_by_index(block_index)
        if block is None:
            self._error(404, f"Block {block_index} not found")
            return
        self._send_json(block)

    def _handle_verification(self, qs: dict) -> None:
        """`GET /api/verification?limit=N` — recent verification results."""
        limit = self._int_param(qs, "limit", 50)
        history = self.context.verification_store.read_history(limit=limit or 50)
        self._send_json(history)

    def _handle_alerts(self, qs: dict) -> None:
        """`GET /api/alerts?limit=N&status=<s>` — alerts filtered by lifecycle status.

        Query params:
          limit  : max alerts to return (default 50)
          status : "active" | "acknowledged" | "resolved" | "unresolved" | "all" (default "all")
        """
        limit = self._int_param(qs, "limit", 50)
        status_filter = self._str_param(qs, "status", "all")

        if self.context.alert_store is not None:
            alerts = self.context.alert_store.get_all_alerts(status=status_filter)
        else:
            # Fallback: read from JSONL if no alert_store
            alerts = self.context.storage.read_alerts()
            alerts = list(reversed(alerts))

        if limit:
            alerts = alerts[:limit]
        self._send_json(alerts)

    # ── POST handlers ─────────────────────────────────────────────────

    def _record_user_action(self, action_type: str, status: str, details: str, session_id: str | None = None, user: str = "admin") -> None:
        """Helper to append an audit action entry to user_activity.jsonl outside watched directory."""
        from datetime import datetime, timezone
        import uuid
        try:
            entry = {
                "event_id": f"act-{uuid.uuid4().hex[:8]}",
                "session_id": session_id or "sess-active",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "user": user,
                "action_type": action_type,
                "status": status,
                "details": details,
            }
            self.context.storage.append_user_activity(entry)
        except Exception:
            logger.exception("Failed to record user action in audit log")

    def _handle_alert_acknowledge(self, alert_id: str) -> None:
        """`POST /api/alerts/<id>/acknowledge` — acknowledge an alert."""
        self._drain_body()
        if self.context.alert_store is None:
            self._error(501, "Alert store not initialized")
            return
        success = self.context.alert_store.acknowledge_alert(alert_id)
        if success:
            alert = self.context.alert_store.get_alert_by_id(alert_id)
            self._record_user_action("ACKNOWLEDGE_ALERT", "SUCCESS", f"Acknowledged alert {alert_id!r}.")
            self._send_json({
                "success": True,
                "alert_id": alert_id,
                "status": "acknowledged",
                "alert": alert,
            })
        else:
            self._error(404, f"Alert {alert_id!r} not found or already resolved")

    def _handle_run_verification(self) -> None:
        """`POST /api/actions/run-verification` — manual verification trigger."""
        self._drain_body()
        result = self.context.daemon.run_once()
        # Include alert lifecycle summary in response
        response = result.to_dict()
        if self.context.alert_store is not None:
            response["alert_counts"] = self.context.alert_store.get_counts()
        chain_state = self.context.state_manager.get_chain_state()
        response["chain_state"] = chain_state
        response["append_enabled"] = self.context.state_manager.is_append_enabled()
        self._record_user_action("RUN_VERIFICATION", "SUCCESS", f"Triggered manual chain verification. Result: {result.blocks_checked} blocks verified healthy (verification_id: {result.verification_id}).")
        self._send_json(response)

    def _handle_checkpoints(self) -> None:
        """`GET /api/checkpoints` — list all backup checkpoints."""
        checkpoints = self.context.storage.list_checkpoints()
        self._send_json({"checkpoints": checkpoints})

    def _handle_restore_checkpoint(self) -> None:
        """`POST /api/actions/restore-checkpoint` — restore ledger from immutable backup."""
        body = self._read_body_json()
        filename = body.get("checkpoint_filename")
        try:
            restore_res = self.context.storage.restore_from_checkpoint(filename)
            # Run verification and state machine immediately to unfreeze upon restore
            verification_result = self.context.daemon.run_once()
            restore_res["verification"] = verification_result.to_dict()
            restore_res["chain_state"] = self.context.state_manager.get_chain_state()
            restore_res["append_enabled"] = self.context.state_manager.is_append_enabled()
            self._record_user_action("RESTORE_CHECKPOINT", "SUCCESS", f"Restored active ledger from checkpoint {restore_res.get('restored_from')!r} ({restore_res.get('blocks_restored')} blocks restored).")
            self._send_json(restore_res)
        except Exception as exc:
            logger.exception("Failed to restore from checkpoint")
            self._error(500, str(exc))

    def _handle_exports(self) -> None:
        """`POST /api/exports` — export a data bundle.

        Accepts JSON body::

            {
                "type": "full" | "events" | "alerts" | "verification" | "incident",
                "format": "json" | "markdown" | "html",
                "from_index": N,
                "to_index": M,
                "time_from": "ISO",
                "time_to": "ISO",
                "file_name": "test_log.log",
                "change_type": "data_added",
                "alert_id": "alt-000001",
                "incident_id": "block-7-hash_mismatch"
            }
        """
        from backend.core.normalizer import _normalize_timestamp
        body = self._read_body_json()
        export_type = body.get("type", "full")
        export_format = body.get("format", "json")
        from_index = body.get("from_index")
        to_index = body.get("to_index")
        time_from = body.get("time_from", "")
        time_to = body.get("time_to", "")
        file_name_filter = (body.get("file_name") or "").lower()
        change_type_filter = body.get("change_type", "")
        alert_id_filter = body.get("alert_id", "")
        incident_id_filter = body.get("incident_id", "")

        valid_types = {"full", "events", "alerts", "verification", "incident"}
        if export_type not in valid_types:
            self._error(400, f"Invalid export type. Must be one of: {sorted(valid_types)}")
            return

        valid_formats = {"json", "markdown", "html"}
        if export_format not in valid_formats:
            self._error(400, f"Invalid format. Must be one of: {sorted(valid_formats)}")
            return

        exported_at = _normalize_timestamp(None)
        data: list = []
        state = self.context.state_manager.get_state()

        # --- Collect data ---
        if export_type in ("full", "events"):
            blocks = self._filter_records(self.context.storage.read_all_blocks(), time_from, time_to, file_name_filter, change_type_filter, from_index, to_index, is_block=True, alert_id=alert_id_filter, incident_id=incident_id_filter)
            data = [b for b in blocks if b.get("event_type") != "genesis"] if export_type == "events" else blocks

        elif export_type == "alerts":
            all_alerts = self.context.alert_store.get_all_alerts() if self.context.alert_store is not None else self.context.storage.read_alerts()
            data = self._filter_records(all_alerts, time_from, time_to, file_name=file_name_filter, change_type=change_type_filter, from_index=from_index, to_index=to_index, ts_key="created_at", alert_id=alert_id_filter, incident_id=incident_id_filter)

        elif export_type == "verification":
            data = self.context.verification_store.read_history(limit=1000)
            if time_from: data = [r for r in data if (r.get("timestamp_utc") or "") >= time_from]
            if time_to: data = [r for r in data if (r.get("timestamp_utc") or "") <= time_to]

        elif export_type == "incident":
            # Bundle everything related to a specific incident
            if not incident_id_filter and not alert_id_filter:
                self._error(400, "incident export requires incident_id or alert_id")
                return
            # Resolve incident_id from alert_id if needed
            if not incident_id_filter and alert_id_filter and self.context.alert_store is not None:
                alert = self.context.alert_store.get_alert_by_id(alert_id_filter)
                if alert:
                    incident_id_filter = alert.get("incident_key", "")
            # Gather all alerts for this incident
            if self.context.alert_store is not None:
                inc_alerts = [
                    a for a in self.context.alert_store.get_all_alerts()
                    if a.get("incident_key") == incident_id_filter
                ]
            else:
                inc_alerts = []
            inc_alerts = self._filter_records(inc_alerts, time_from, time_to, file_name=file_name_filter, change_type=change_type_filter, from_index=from_index, to_index=to_index, ts_key="created_at")
            incident_block_indices = {a.get("block_index") for a in inc_alerts if a.get("block_index") is not None}
            all_blocks = self.context.storage.read_all_blocks()
            incident_blocks = [b for b in all_blocks if b.get("block_index") in incident_block_indices]
            incident_blocks = self._filter_records(incident_blocks, time_from, time_to, file_name=file_name_filter, change_type=change_type_filter, from_index=from_index, to_index=to_index, is_block=True)
            data = [
                {"type": "incident_summary", "incident_key": incident_id_filter, "alerts": inc_alerts},
                {"type": "related_blocks", "blocks": incident_blocks},
            ]

        export_id = f"exp-{id(data):016x}"

        if export_format == "json":
            self._record_user_action("EXPORT_DATA", "SUCCESS", f"Exported bundle of type {export_type!r} in format 'json' ({len(data)} records).")
            self._send_json({
                "export_id": export_id,
                "exported_at": exported_at,
                "type": export_type,
                "format": "json",
                "record_count": len(data),
                "data": data,
                "state": state,
            })
        elif export_format in ("markdown", "html"):
            report = _build_human_report(
                export_type=export_type,
                export_id=export_id,
                exported_at=exported_at,
                data=data,
                state=state,
                fmt=export_format,
            )
            ct = "text/html; charset=utf-8" if export_format == "html" else "text/plain; charset=utf-8"
            self._record_user_action("EXPORT_DATA", "SUCCESS", f"Exported bundle of type {export_type!r} in format {export_format!r} ({len(data)} records).")
            self._send_json({
                "export_id": export_id,
                "exported_at": exported_at,
                "type": export_type,
                "format": export_format,
                "record_count": len(data),
                "report": report,
            })

    def _handle_auth_login(self) -> None:
        """`POST /api/auth/login` — record user login and start session audit."""
        from datetime import datetime, timezone
        import uuid
        body = self._read_body_json()
        user = body.get("user", "admin")
        role = body.get("role", "system_administrator")
        session_id = body.get("session_id") or f"sess-{uuid.uuid4().hex[:6]}"
        entry = {
            "event_id": f"act-{uuid.uuid4().hex[:8]}",
            "session_id": session_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "user": user,
            "role": role,
            "action_type": "LOGIN",
            "status": "SUCCESS",
            "ip_address": self.client_address[0] if hasattr(self, "client_address") and self.client_address else "127.0.0.1",
            "details": f"User {user!r} ({role}) authenticated and initiated session.",
        }
        try:
            self.context.storage.append_user_activity(entry)
            self._send_json({"success": True, "session": entry})
        except Exception as exc:
            logger.exception("Failed to record login")
            self._error(500, str(exc))

    def _handle_auth_logout(self) -> None:
        """`POST /api/auth/logout` — record user logout and session summary."""
        from datetime import datetime, timezone
        import uuid
        body = self._read_body_json()
        session_id = body.get("session_id", "sess-default")
        user = body.get("user", "admin")
        
        # Calculate duration and actions count if history exists
        entries = self.context.storage.read_user_activity(session_id=session_id)
        duration_sec = 0
        actions_count = 0
        if entries:
            actions_count = len([e for e in entries if e.get("action_type") not in ("LOGIN", "LOGOUT")])
            try:
                login_entry = next((e for e in entries if e.get("action_type") == "LOGIN"), entries[-1])
                t0 = datetime.fromisoformat(login_entry["timestamp_utc"])
                t1 = datetime.now(timezone.utc)
                duration_sec = int((t1 - t0).total_seconds())
            except Exception:
                pass

        entry = {
            "event_id": f"act-{uuid.uuid4().hex[:8]}",
            "session_id": session_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "user": user,
            "action_type": "LOGOUT",
            "status": "SUCCESS",
            "duration_seconds": duration_sec,
            "actions_performed_count": actions_count,
            "details": f"User {user!r} logged out cleanly after {duration_sec}s ({actions_count} actions performed).",
        }
        try:
            self.context.storage.append_user_activity(entry)
            self._send_json({"success": True, "session": entry})
        except Exception as exc:
            logger.exception("Failed to record logout")
            self._error(500, str(exc))

    def _handle_get_audit_activity(self, qs: dict[str, list[str]]) -> None:
        """`GET /api/audit/activity` — return chronological user activity and session logs."""
        session_id = qs.get("session_id", [None])[0]
        entries = self.context.storage.read_user_activity(session_id=session_id)
        entries.sort(key=lambda x: x.get("timestamp_utc", ""), reverse=True)
        self._send_json({"activity": entries})


# ── Human-readable report builder ────────────────────────────────────


def _build_human_report(
    export_type: str,
    export_id: str,
    exported_at: str,
    data: list,
    state: dict,
    fmt: str = "markdown",
) -> str:
    """
    Generate a human-readable Markdown or HTML evidence report.

    Parameters
    ----------
    export_type, export_id, exported_at, data, state, fmt
        Report parameters.

    Returns
    -------
    str
        Markdown or HTML report string.
    """
    chain_state = str(state.get("chain_state") or state.get("health_status") or "unknown")
    append_enabled = state.get("append_enabled", not state.get("frozen", False))
    first_invalid = state.get("first_invalid_block")
    last_resolved = state.get("last_resolved_incident")
    active_count = state.get("active_alert_count", 0)
    resolved_count = state.get("resolved_alert_count", 0)
    total_verifications = state.get("total_verifications", 0)
    last_verified = state.get("last_verification_utc", "—")

    lines: list[str] = []

    if fmt == "markdown":
        lines += [
            f"# MicroLedger SOC — Evidence Report",
            f"",
            f"| Field | Value |",
            f"|---|---|",
            f"| Export ID | `{export_id}` |",
            f"| Generated At | {exported_at} |",
            f"| Export Type | {export_type} |",
            f"| Records | {len(data)} |",
            f"",
            f"---",
            f"",
            f"## Current Chain Status",
            f"",
            f"| Metric | Value |",
            f"|---|---|",
            f"| Chain State | **{chain_state.upper()}** |",
            f"| Append Operations | {'✅ Active' if append_enabled else '🔒 Frozen'} |",
            f"| First Invalid Block | {first_invalid if first_invalid is not None else '—'} |",
            f"| Active Alerts | {active_count} |",
            f"| Resolved Incidents | {resolved_count} |",
            f"| Total Verifications | {total_verifications} |",
            f"| Last Verified | {last_verified} |",
            f"",
        ]

        summary_status = f"The ledger is currently **{chain_state.upper()}** with append operations {'enabled' if append_enabled else 'frozen'}."
        incident_note = f"There are {active_count} active integrity alerts and {resolved_count} resolved incidents recorded." if (active_count or resolved_count) else "No active integrity issues are present on the chain."
        lines += [
            f"## Executive Summary",
            f"",
            f"This evidence bundle captures **{len(data)} records** under the `{export_type}` export profile generated on {exported_at}. {summary_status} {incident_note}",
            f"",
        ]

        if first_invalid is not None:
            lines += [
                f"## ⚠️ Active Incident",
                f"",
                f"**Block {first_invalid}** is the first block with an integrity failure.",
                f"Chain state is **BROKEN** and append operations are **FROZEN** until the",
                f"ledger is repaired and a clean verification pass succeeds.",
                f"",
            ]

        if last_resolved:
            lines += [
                f"## ✅ Last Resolved Incident",
                f"",
                f"| Field | Value |",
                f"|---|---|",
                f"| Alert ID | `{last_resolved.get('alert_id', '—')}` |",
                f"| Incident Key | `{last_resolved.get('incident_key', '—')}` |",
                f"| Severity | {last_resolved.get('severity', '—')} |",
                f"| Resolved At | {last_resolved.get('resolved_at', '—')} |",
                f"| Resolved By | `{last_resolved.get('resolved_by_verification', '—')}` |",
                f"",
            ]

        # Collect blocks for statistics
        blocks_in_data = [b for b in data if isinstance(b, dict) and b.get("block_index") is not None and b.get("event_type") != "incident_summary"]
        if export_type == "incident":
            for item in data:
                if isinstance(item, dict) and item.get("type") == "related_blocks":
                    blocks_in_data = item.get("blocks", [])

        # Build what changed statistics
        change_counts = {}
        modified_files = set()
        for b in blocks_in_data:
            if b.get("event_type") == "genesis":
                continue
            log_data = b.get("log_data") or {}
            ct = log_data.get("change_type") or b.get("event_type") or "other"
            change_counts[ct] = change_counts.get(ct, 0) + 1
            src = b.get("source_identifier") or b.get("source_path")
            if src:
                modified_files.add(str(src))

        lines += [
            f"## What Changed",
            f"",
            f"During the captured period across {len(blocks_in_data)} block(s), {len(modified_files)} unique source(s) experienced activity.",
            f"",
            f"| Change Category | Occurrences |",
            f"|---|---|",
        ]
        if change_counts:
            for ct, cnt in sorted(change_counts.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"| `{ct}` | {cnt} |")
        else:
            lines.append(f"| No changes recorded | 0 |")
        lines.append("")
        if modified_files:
            lines.append(f"**Affected Sources:** " + ", ".join(f"`{f}`" for f in sorted(modified_files)[:20]))
            lines.append("")

        # Collect alerts for what was resolved
        alerts_in_data = []
        if export_type == "alerts":
            alerts_in_data = data
        elif export_type in ("full", "incident"):
            for item in data:
                if isinstance(item, dict) and item.get("type") == "incident_summary":
                    alerts_in_data = item.get("alerts", [])

        resolved_alerts = [a for a in alerts_in_data if isinstance(a, dict) and a.get("status") == "resolved"]
        lines += [
            f"## What Was Resolved",
            f"",
        ]
        if resolved_alerts or last_resolved:
            if last_resolved:
                lines += [
                    f"**Historical Resolved Incident:** Alert `{last_resolved.get('alert_id', '—')}` (`{last_resolved.get('incident_key', '—')}`) was resolved at {last_resolved.get('resolved_at', '—')} by verification pass `{last_resolved.get('resolved_by_verification', '—')}`.",
                    f"",
                ]
            if resolved_alerts:
                lines += [
                    f"| Alert ID | Severity | Failure Type | Block | Resolved At |",
                    f"|---|---|---|---|---|",
                ]
                for ra in resolved_alerts[:30]:
                    lines.append(
                        f"| `{ra.get('alert_id', '—')}` "
                        f"| {ra.get('severity', '—')} "
                        f"| {ra.get('failure_type', '—')} "
                        f"| #{ra.get('block_index', '—')} "
                        f"| {(ra.get('resolved_at') or '')[:19]} |"
                    )
                lines.append("")
        else:
            lines += [
                f"No resolved incidents or historical resolved alerts captured in this export period.",
                f"",
            ]

        # Alert summary
        alerts_in_data = []
        if export_type == "alerts":
            alerts_in_data = data
        elif export_type in ("full", "incident"):
            for item in data:
                if isinstance(item, dict) and item.get("type") == "incident_summary":
                    alerts_in_data = item.get("alerts", [])

        if alerts_in_data:
            lines += [
                f"## Alert Summary",
                f"",
                f"| Alert ID | Status | Severity | Failure Type | Block | Created |",
                f"|---|---|---|---|---|---|",
            ]
            for a in alerts_in_data[:50]:
                lines.append(
                    f"| `{a.get('alert_id', '—')}` "
                    f"| {a.get('status', '—')} "
                    f"| {a.get('severity', '—')} "
                    f"| {a.get('failure_type', '—')} "
                    f"| {a.get('block_index', '—')} "
                    f"| {(a.get('created_at') or '')[:19]} |"
                )
            lines.append("")

        # Block summary
        blocks_in_data = [b for b in data if isinstance(b, dict) and b.get("block_index") is not None and b.get("event_type") != "incident_summary"]
        if export_type == "incident":
            for item in data:
                if isinstance(item, dict) and item.get("type") == "related_blocks":
                    blocks_in_data = item.get("blocks", [])

        if blocks_in_data:
            lines += [
                f"## Block Summary ({len(blocks_in_data)} blocks)",
                f"",
                f"| # | Event Type | Change Type | Source | Timestamp |",
                f"|---|---|---|---|---|",
            ]
            for b in blocks_in_data[:100]:
                log_data = b.get("log_data") or {}
                change_type = log_data.get("change_type", "—")
                lines.append(
                    f"| {b.get('block_index', '—')} "
                    f"| {b.get('event_type', '—')} "
                    f"| {change_type} "
                    f"| {b.get('source_identifier', '—')} "
                    f"| {(b.get('timestamp_utc') or '')[:19]} |"
                )
            lines.append("")

        lines += [
            "---",
            "",
            f"*Report generated by MicroLedger SOC Console. This report is tamper-evident.*",
            f"*Chain signatures can be independently verified against the ledger blocks.*",
        ]

        return "\n".join(lines)

    else:
        # HTML report
        md = _build_human_report(export_type, export_id, exported_at, data, state, fmt="markdown")
        import html as html_mod
        html_lines = [
            '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">',
            f'<title>MicroLedger Evidence Report — {export_id}</title>',
            '<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#cbd5e1;margin:0;padding:2rem;} h1,h2,h3{color:#f1f5f9;} table{border-collapse:collapse;width:100%;margin:1rem 0;} th,td{border:1px solid #334155;padding:0.5rem 0.75rem;text-align:left;} th{background:#1e293b;color:#94a3b8;} code{background:#1e293b;padding:0.1rem 0.3rem;border-radius:3px;font-size:0.85em;} hr{border-color:#334155;} .healthy{color:#34d399;} .broken{color:#f87171;} .degraded{color:#fbbf24;}</style></head><body>',
        ]
        for line in md.split("\n"):
            if line.startswith("# "): html_lines.append(f"<h1>{html_mod.escape(line[2:])}</h1>")
            elif line.startswith("## "): html_lines.append(f"<h2>{html_mod.escape(line[3:])}</h2>")
            elif line.startswith("### "): html_lines.append(f"<h3>{html_mod.escape(line[4:])}</h3>")
            elif line.startswith("|"):
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if all(c.startswith("---") for c in cells): continue
                tag = "th" if "---" in line else "td"
                html_lines.append("<tr>" + "".join(f"<{tag}>{html_mod.escape(c)}</{tag}>" for c in cells) + "</tr>")
            elif line.strip() == "---": html_lines.append("<hr>")
            elif not line.strip(): html_lines.append("<br>")
            else: html_lines.append(f"<p>{html_mod.escape(line)}</p>")
        html_lines.extend(["</body>", "</html>"])
        return "\n".join(html_lines)
