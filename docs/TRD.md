> [!NOTE]
> **Project Status: Implemented & Complete**
> All phases (1-4) outlined in this document have been fully implemented.
> These documentation files have been consolidated into the docs/ directory for better organization.
# Technical Requirements Document

## Document Purpose
This document defines the technical ground truth for the data model, hashing rules, storage behavior, runtime limits, process boundaries, and local interface contracts of the Zero-Trust Localized Micro-Ledger system.

## System Overview
The system consists of:
- A Python event capture and ledger append engine.
- A Python verification daemon loop.
- A local state exposure layer for the dashboard.
- A React/Tailwind dashboard that consumes read-only local API state.

## Canonical Data Model

### Ledger Storage Format
Version 1 shall use line-delimited JSON (`.jsonl`) as the canonical ledger format.

Properties:
- One block per line
- UTF-8 encoding
- Newline-delimited records
- No in-place updates after append

### Required Ledger Files
- `ledger/current/ledger.jsonl`
- `ledger/current/state.json`
- `ledger/current/alerts.jsonl`
- `ledger/archive/*.jsonl`
- `ledger/checkpoints/*.json`

## Single Ledger Block Schema
```json
{
  "schema_version": "1.0",
  "block_index": 1,
  "timestamp_utc": "2026-07-15T14:22:14.123Z",
  "event_type": "file_modified",
  "source_type": "config_file",
  "source_path": "/etc/device.conf",
  "source_identifier": "device.conf",
  "event_id": "evt-000001",
  "log_data": {
    "summary": "configuration value changed",
    "raw_line": null,
    "snapshot_sha256": "a1b2c3...",
    "metadata": {
      "actor": "system",
      "encoding": "utf-8",
      "size_bytes": 248
    }
  },
  "previous_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "current_hash": "f3c9...",
  "ingest_sequence": 1,
  "verification_hint": {
    "segment_id": "segment-0001",
    "expected_chain_state": "healthy"
  }
}
```

## Canonical Serialization Rule
Before hashing, the block payload shall be serialized with:
1. UTF-8 encoding
2. Normalized line endings (`\n`)
3. Predictable replacement for invalid byte sequences
4. Sorted JSON keys
5. Compact separators with no non-semantic whitespace
6. Exclusion of `current_hash` from the preimage
7. Exact preservation of null, numeric, and boolean values

## Hashing Rule
### Digest Algorithm
SHA-256 from Python `hashlib`

### Concatenation Rule
Let:
- `P` = `previous_hash`
- `S` = canonical serialized block excluding `current_hash`

Then:
`current_hash = SHA256(P || S)`

## Verification Rules
Each verification pass must confirm:
1. Valid JSON
2. Required fields present
3. Monotonic and contiguous `block_index`
4. `previous_hash` matches prior block `current_hash`
5. Recomputed hash equals stored `current_hash`
6. No unexpected truncation
7. Segment metadata is internally consistent

## Resource Constraints
### CPU
- Idle/low event load target: < 5% of one core
- Sustained usage target: < 20% of one core

### Memory
- Baseline Python core target: < 100 MB
- Preferred steady state: < 64 MB
- Verifier must stream line-by-line

### Storage
- Active ledger segment rotation threshold: 5 MB or 10,000 blocks
- Alert log rotation threshold: 1 MB
- State file target: < 128 KB

## IPC Mechanism for Frontend
Expose local read-only state using a Python local HTTP server bound only to `127.0.0.1`.

### Minimum Endpoints
- `GET /api/health`
- `GET /api/state`
- `GET /api/files`
- `GET /api/events`
- `GET /api/ledger`
- `GET /api/ledger/:block_index`
- `GET /api/verification`
- `GET /api/alerts`
- `POST /api/actions/run-verification`
- `POST /api/exports`

## Recovery Model
Version 1 supports controlled recovery mode only, not automatic repair.

