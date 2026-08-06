# Project RPC Implementation Analysis And Backup Runbook

## Current RPC Implementation Map

### 1. Shared client pattern
- API, Wallet, and Explorer initialize evrmore-rpc client from RPC_DATADIR.
- Primary pattern is local node access via the node data directory and evrmore.conf.

### 2. API layer implementation
- File: Tome/API/rpc.py
- Provides EvrmoreRPC wrapper class with grouped methods for:
  - addressindex
  - assets and NFT helpers
  - blockchain and mempool
  - messages and mining
- Exposes global singleton instance named evrmore_rpc used by API views.

### 3. Wallet layer implementation
- File: Tome/Wallet/rpc.py
- Contains production transaction assembly helpers for:
  - EVR transfers
  - asset transfers
  - asset issuance and reissue
  - restricted and qualifier asset operations
  - atomic asset-for-EVR swap transaction flow
- Includes fee estimation fallback logic and multi-strategy signing fallback.

### 4. Explorer implementation
- Files: Tome/Explorer/rpc.py and Tome/Explorer/views.py
- Uses generic execute_command_sync calls for read-only chain and tx exploration.
- Includes demo-mode fallback in views when RPC calls fail.

### 5. Other direct RPC consumers
- Listings, Media, and Wallet views call RPC methods directly for balance checks, signatures, and metadata flows.

## Strengths In Current Design
- Clear wrapper in API for most command families.
- Wallet transaction builder has explicit fee, dust, and UTXO handling.
- Explorer has graceful degradation for UI continuity.
- Tests already mock key RPC touchpoints in API and Wallet.

## Implementation Risks To Track
- Configuration is datadir-centric; there is no project-level central abstraction for remote RPC URL/auth fallback.
- RPC access style is mixed:
  - wrapper-driven in API
  - helper-function-driven in Wallet
  - direct RPC calls in multiple views
- Public RPC endpoints may be reachable but whitelist-restricted, so relying on them for full app behavior is unsafe.

## Backup Strategy

### Tier 1: Local node as authoritative fallback
1. Ensure a local Evrmore node is running and synced.
2. Ensure evrmore.conf has rpcuser, rpcpassword, and rpcport.
3. Set RPC_DATADIR to the matching node datadir for Django and tooling.
4. Validate baseline with the local probe script in this skill.

### Tier 2: Wrapper-preserving fallback mode
1. Keep existing module interfaces unchanged.
2. Use local node RPC only, not public RPC, for state-changing operations.
3. Restrict public endpoints to optional observational checks.

### Tier 3: Read-only degradation mode
1. For explorer-like surfaces, provide non-blocking fallback messaging.
2. Do not attempt signing/broadcast while RPC health is degraded.

## Backup Validation Procedure
1. Run local probe:
- /Users/chiefton/Documents/GitHub/DeFiTome/.venv/bin/python .github/skills/evrmore-engineer/scripts/local_rpc_backup_probe.py

2. Run existing project RPC checklist validation:
- /Users/chiefton/Documents/GitHub/DeFiTome/.venv/bin/python scripts/verify_rpc_cheatsheet.py

3. Run Django checks:
- /Users/chiefton/Documents/GitHub/DeFiTome/.venv/bin/python Tome/manage.py check

4. Run focused tests:
- /Users/chiefton/Documents/GitHub/DeFiTome/.venv/bin/python Tome/manage.py test API Wallet

## Operational Backup Rules
- Treat local node RPC as required for:
  - signing
  - broadcasting
  - UTXO-critical decision paths
- If endpoint responses include whitelist restriction errors, classify as restricted access rather than full outage.
- Preserve deterministic transaction construction outputs for auditability.

## Suggested Next Hardening Step
- Introduce one thin project-level RPC gateway module that standardizes:
  - health classification
  - method call telemetry
  - fallback routing policy
while preserving existing public function signatures.
