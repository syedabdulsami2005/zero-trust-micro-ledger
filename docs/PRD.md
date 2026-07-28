> [!NOTE]
> **Project Status: Implemented & Complete**
> All phases (1-4) outlined in this document have been fully implemented.
> These documentation files have been consolidated into the docs/ directory for better organization.
# Project Requirements Document

## Project Title
Zero-Trust Localized Micro-Ledgers for Edge-Sensor Firmware Integrity

## Document Purpose
This document defines the product vision, target users, functional requirements, constraints, scope boundaries, and success criteria for an offline-first tamper-evident local logging system for edge devices.

## Product Summary
Edge sensors, local gateways, and embedded systems often store logs and configuration state on the same device that may later be compromised. If an attacker gains administrative or physical access, they can modify, truncate, or delete local evidence to hide actions. This project provides a lightweight local micro-ledger implemented in Python that captures critical local events and stores them as sequential hash-linked blocks. A background verifier continuously re-checks the ledger, while a local administrative dashboard presents system health, alerts, and evidence views.

## Problem Statement
Traditional local logs are easy to alter after compromise because they are commonly stored as ordinary files without cryptographic linkage or verifiable integrity guarantees. Cloud logging helps centralization, but it does not solve offline or network-isolated environments. This project addresses that gap by treating every security-relevant local event as a chained record whose historical integrity can be validated later.

## Vision
Build a minimal but rigorous local integrity platform for edge devices that:
- Works fully offline.
- Uses only Python standard libraries for the security core.
- Stores events as sequential SHA-256 hash-linked blocks.
- Detects tampering rapidly and deterministically.
- Exposes readable local operational state to a browser-based administrative dashboard.
- Can be extended later toward stronger forward-integrity and hardware-assisted anchoring.

## Target Users

### Primary Users
#### 1. Edge Operators
Operators maintain sensors, gateways, and edge compute nodes in remote or low-connectivity environments. They need a simple interface that tells them whether monitored files and logs remain trustworthy, what changed recently, and whether any tamper event requires action.

#### 2. Security Auditors
Auditors need verifiable evidence that important events were recorded, that the chain remained intact over time, and that any modification was detectable and surfaced clearly. They care about chronology, exportability, and evidence quality.

### Secondary Users
- Academic evaluators
- Student developers
- Lab administrators

## User Needs

### Edge Operator Needs
- See overall chain health quickly.
- Identify which files or logs are being monitored.
- Receive clear local alerts when tampering is detected.
- Investigate recent changes by file, time, and severity.
- Continue operation without internet access.

### Auditor Needs
- Verify that each block references the previous block correctly.
- Review exported evidence bundles.
- Confirm that append order, timestamps, and hashes are preserved.
- Distinguish healthy chain states from broken or truncated chains.

## Product Goals
1. Offline integrity protection.
2. Local tamper evidence.
3. Low operational footprint.
4. Explainable security state.
5. Clean academic scope.

## Functional Requirements

### FR-1: Offline Log and File Event Capture
The system shall observe a defined set of local log files, configuration files, and snapshots and create normalized event records when relevant changes occur.

### FR-2: Event Normalization
The system shall convert raw captured input into a stable internal representation so that equivalent data yields consistent hash results across runs.

### FR-3: SHA-256 Micro-Block Generation
The system shall create one ledger block per accepted event using SHA-256 over a deterministic concatenation of selected block fields and the previous block hash.

### FR-4: Sequential Chain Linking
Each block after the genesis block shall include the previous block’s hash and its own current hash.

### FR-5: Append-Oriented Local Storage
The system shall store blocks in append order on local disk using a simple file-based format.

### FR-6: Verification Daemon
The system shall run a background integrity verification loop that periodically replays the chain and detects mismatch conditions.

### FR-7: Tamper Alerting
When verification detects a broken chain or suspicious state, the system shall update local alert state immediately and make it visible to both the backend and dashboard UI.

### FR-8: Local Dashboard
The local dashboard shall display:
- Overall chain health
- Recent events
- Recent blocks
- Verification history
- Alerts
- File watch status
- Drill-down block inspection

### FR-9: Evidence Export
The system shall support export of event history, block ranges, verification reports, and alert summaries.

### FR-10: Safe Degraded Behavior
If the verifier detects corruption, the system shall stop normal append operations until the integrity state is acknowledged or recovery mode is explicitly entered.

## Out of Scope
- Cloud APIs or cloud storage
- External relational databases
- NoSQL services
- Crypto mining, tokens, or distributed consensus
- AI anomaly detection
- Multi-device fleet management
- TPM or secure enclave integration in v1
- Enterprise user authentication
- Remote dashboard hosting

## Non-Goals
This product is not intended to:
- Prevent the initial system compromise
- Replace endpoint protection or IDS
- Guarantee recovery of deleted history
- Provide a decentralized blockchain network

## Assumptions
- The application runs on one local device or workstation.
- The dashboard is served locally.
- The Python security core is the source of truth.
- This system is tamper-evident, not absolutely tamper-proof.

## Acceptance Criteria
The product is minimally complete when:
- It captures changes from at least two watched sources.
- It writes valid sequential blocks locally.
- It verifies the chain periodically.
- It detects manual modification of a past block.
- It halts appending on broken-chain state.
- It exposes local status to the dashboard.
- The dashboard clearly renders healthy and tampered states.

## Success Metrics
- 100% detection of simple historical tampering in controlled tests.
- Deterministic identification of first invalid block.
- No silent continuation after critical verifier-detected corruption.
- Operator can identify chain status within 5 seconds of opening dashboard.

