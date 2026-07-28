# Zero-Trust Localized Micro-Ledger

An offline-first tamper-evident local logging system for edge devices, built with Python and React.

## Overview

Traditional local logs are easy to alter after compromise. This project addresses that gap by treating every security-relevant local event as a chained record whose historical integrity can be validated later using a cryptographic micro-ledger. 

The system consists of three main components:
1. **Core Cryptographic Ledger Engine**: A Python backend that captures events, normalizes them, and appends them to a sequential SHA-256 hash-linked block chain stored in a local `.jsonl` file.
2. **Verification Daemon & Gateway**: A background loop that constantly replays and verifies the chain, coupled with a local REST API that exposes the system state.
3. **Security Operations Center (SOC) Dashboard**: A Vite/React frontend that allows operators to visualize chain health, verify records, monitor files, and export evidence locally.

## Project Status

**All phases (1-4) are fully implemented and complete.** 
The comprehensive documentation for the architecture, design, and technical requirements has been moved to the `docs/` folder.

- **Phase 1**: Core Cryptographic Ledger Engine
- **Phase 2**: Background Integrity Verification Daemon
- **Phase 3**: Local Communication Gateway
- **Phase 4**: Security Operations Center Dashboard (React + Tailwind CSS)

## Directory Structure

- `docs/` - Contains all project documentation (PRD, TRD, Architecture, Rules, etc.)
- `backend/` - The core Python application and gateway API
- `frontend/` - The React and Tailwind CSS dashboard
- `data/` - Holds the local micro-ledger JSONL storage and state
- `run_local.py` - The main Python launcher

## Getting Started

### 1. Start the Backend

Make sure you have Python 3.13+ installed.

```bash
# In the root directory, start the ledger daemon and gateway
py -3.13 run_local.py
```

### 2. Start the Frontend Dashboard

Make sure you have Node.js installed.

```bash
# Open a new terminal, navigate to the frontend folder
cd frontend
npm install
npm run dev
```

The dashboard will be available at `http://localhost:5173`.
