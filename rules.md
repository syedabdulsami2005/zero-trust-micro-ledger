# Absolute Development Guardrails

## Rule 1: Zero reliance on cloud infrastructure or external databases
- No cloud APIs
- No SaaS logging platforms
- No external DBs
- Local files are the source of truth
- Frontend must work from local API state only

## Rule 2: Strict cryptographic boundary conditions
If verification fails, append operations must halt immediately to prevent chain poisoning.

## Rule 3: Robust exception handling
The daemon must not crash because of:
- invalid bytes
- unexpected encoding
- partial lines
- filesystem errors

## Rule 4: Deterministic serialization is mandatory
- Sorted JSON keys
- Stable timestamp format
- Fixed separators
- Exclude `current_hash` from preimage

## Rule 5: Single writer, controlled readers
- Only one write path may append
- UI never appends directly
- Verification and API reads must be safe

## Rule 6: UI is not a security authority
- Frontend does not compute truth
- No client-side hash generation
- No client-side ledger mutation

## Rule 7: Every critical failure becomes structured state
- Verification failure -> alert object
- Source-watch failure -> monitored-source warning

## Rule 8: Historical records are append-only
- No block update path
- No block delete path
- Rotation moves files but does not alter block contents
