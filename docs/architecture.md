> [!NOTE]
> **Project Status: Implemented & Complete**
> All phases (1-4) outlined in this document have been fully implemented.
> These documentation files have been consolidated into the docs/ directory for better organization.
# System Architecture Document

## Architecture Goals
The architecture must preserve:
1. Simple local deployment
2. Deterministic data flow
3. Separation of security core and UI
4. Explicit offline-first operation

## High-Level Architecture
The application has three local layers:
- Python security core
- Local API/server layer
- React/Tailwind dashboard layer

## Required Chronological Data Flow
Raw Log Event
-> Hashing/Chaining Engine
-> Local Storage Append
-> Daemon Verification Loop
-> Local Web API Endpoint
-> UI State Update

## Recommended Folder Layout
```text
zero-trust-micro-ledger/
├── docs/
│   ├── PRD.md
│   ├── TRD.md
│   ├── architecture.md
│   ├── rules.md
│   ├── phases.md
│   └── design.md
├── backend/
│   ├── core/
│   ├── capture/
│   ├── daemon/
│   ├── api/
│   ├── exports/
│   ├── tests/
│   └── run_local.py
├── data/
│   ├── ledger/
│   ├── exports/
│   ├── watched/
│   └── runtime/
├── frontend/
│   ├── public/
│   ├── src/
│   ├── tailwind.config.js
│   └── package.json
├── scripts/
└── README.md
```

## Component Responsibilities
### Core
- `normalizer.py`: deterministic event normalization
- `hasher.py`: canonical preimage creation and SHA-256 hashing
- `ledger_engine.py`: block creation and append discipline
- `storage.py`: JSONL append/read/rotation
- `verifier.py`: replay and validation
- `alerts.py`: tamper alert creation
- `state_manager.py`: current runtime state
- `recovery.py`: controlled recovery operations

### Capture Layer
Reads watched source changes and forwards normalized events to core.

### Daemon Layer
Runs periodic verification, polling, and housekeeping.

### API Layer
Exposes trusted local state without bypassing the core.

### Frontend Layer
Visualizes health, events, blocks, alerts, and exports.

