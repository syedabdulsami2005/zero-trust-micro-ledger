#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8765}"

echo "== Create watched file =="
curl -sS -X POST "$BASE_URL/api/files/write" \
  -H 'Content-Type: application/json' \
  -d '{"path":"demo/operator_note.txt","content":"initial remediation note"}'
echo

echo "== Read watched file content =="
curl -sS "$BASE_URL/api/files/content?path=demo/operator_note.txt"
echo

echo "== Manual edit via alert resolve flow (requires unresolved alert id) =="
echo "curl -X POST $BASE_URL/api/alerts/resolve -H 'Content-Type: application/json' -d '{\"alert_id\":\"<alert-id>\",\"resolution_action\":\"manual_edit\",\"path\":\"demo/operator_note.txt\",\"content\":\"updated note\"}'"

echo "== Delete watched file =="
curl -sS -X POST "$BASE_URL/api/files/delete" \
  -H 'Content-Type: application/json' \
  -d '{"path":"demo/operator_note.txt"}'
echo
