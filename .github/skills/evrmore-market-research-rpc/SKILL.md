---
name: evrmore-market-research-rpc
description: "Research and trade EVRMore with an engineering-first workflow. Use when analyzing EVRMore fundamentals, mapping official and third-party links, validating RPC data, producing risk-bounded day-trading plans, and defining an EVRMore-native DEX that transacts exclusively with on-chain assets."
argument-hint: "goal=<market-scan|trade-plan|rpc-health|dex-architecture> network=<mainnet|testnet|both> horizon=<intraday|swing> risk=<low|medium|high>"
user-invocable: true
---

# EVRMore Market Research And RPC-Driven Trading

Build a repeatable workflow for EVRMore market analysis, execution planning, and DEX architecture by combining:
- source-document review
- live chain telemetry from public RPC
- explicit risk controls and validation gates

This skill is for analysis and planning. It does not guarantee outcomes and should not bypass your risk controls.

## Resources
- RPC health script: [rpc_health_check.py](./scripts/rpc_health_check.py)
- Local node backup probe: [local_rpc_backup_probe.py](./scripts/local_rpc_backup_probe.py)
- Trading session report template: [trading-session-report-template.md](./assets/trading-session-report-template.md)
- DEX architecture template: [dex-architecture-template.md](./assets/dex-architecture-template.md)
- DEX threat model template: [dex-threat-model-template.md](./assets/dex-threat-model-template.md)
- DEX rollout checklist: [dex-rollout-checklist.md](./assets/dex-rollout-checklist.md)
- RPC method reference pack: [rpc-method-pack.md](./references/rpc-method-pack.md)
- Project RPC backup runbook: [project-rpc-implementation-backup.md](./references/project-rpc-implementation-backup.md)

## When To Use
- You need a structured EVRMore research pass before taking a trade.
- You want to validate claims with live on-chain RPC data.
- You need a daily or session-based trading plan with hard limits.
- You want reproducible notes that can be audited later.
- You want to design a DEX flow that settles exclusively with native on-chain EVRMore assets.

## Inputs
- `goal`: `market-scan`, `trade-plan`, `rpc-health`, or `dex-architecture`
- `network`: `mainnet`, `testnet`, or `both`
- `horizon`: `intraday` or `swing`
- `risk`: `low`, `medium`, `high`
- Optional watchlist pairs and session window

## Required Public Endpoints
Use these as first choice endpoints:
- `https://evr-rpc-mainnet.evrmorecoin.org/rpc`
- `https://evr-rpc-testnet.evrmorecoin.org/rpc`

Important:
- The host root (`/`) returns `Cannot POST /`.
- JSON-RPC is served at `/rpc`.

## Procedure

1. Define mission and constraints
- State the objective in one sentence: discovery, setup, or execution plan.
- Set hard constraints first:
  - max risk per trade
  - max daily drawdown
  - max concurrent positions
  - no-trade conditions (low liquidity, unstable RPC, abnormal spreads)
- Pick analysis horizon (`intraday` or `swing`) and network.

2. Build the EVRMore knowledge map
- Start with official sources:
  - `https://evrmorecoin.org/`
  - `https://evrmorecoin.org/docs/`
  - `https://evrmorecoin.org/3rd_party_links/`
  - `https://evrmorecoin.org/downloads/`
  - `https://evrmorecoin.org/other/`
- Follow each relevant sublink and classify as:
  - protocol fundamentals
  - wallet and node operations
  - exchange/liquidity venue
  - community/news/sentiment
- Capture date, URL, key claim, and whether on-chain evidence is available.

3. Probe RPC health and capability
- Run a minimal health check on target network:
  - `getblockchaininfo`
  - `getbestblockhash`
  - `getmempoolinfo`
- Confirm the chain (`main` or `test`) matches requested scope.
- Retrieve command discovery via `help` when uncertain about method names.
- Prefer script-based checks for repeatability:
  - `python .github/skills/evrmore-market-research-rpc/scripts/rpc_health_check.py --network both`
  - if local CA trust is missing, temporary fallback:
    - `python .github/skills/evrmore-market-research-rpc/scripts/rpc_health_check.py --network both --insecure`
- Interpret health output explicitly:
  - `access_mode=full`: read access available for health and telemetry calls.
  - `access_mode=restricted`: endpoint is reachable but method access is whitelist-restricted.
  - `access_mode=unreachable`: endpoint could not be reached.

Example command:
```bash
curl -sS -X POST https://evr-rpc-mainnet.evrmorecoin.org/rpc \
  -H 'content-type: application/json' \
  --data '{"jsonrpc":"1.0","id":"scan","method":"getblockchaininfo","params":[]}'
```

4. Pull market-relevant on-chain signals
- Collect block cadence and liveness:
  - `blocks`, `headers`, `mediantime`, `verificationprogress`
- Collect congestion and execution pressure:
  - `getmempoolinfo` (`size`, `bytes`, fee-related fields when available)
- Collect asset and address signals relevant to EVR trading thesis:
  - `listassets` for discovery windows
  - `getassetdata` for specific assets
  - `getaddressbalance` or `getaddressutxos` for monitored addresses
- Timebox data pulls and annotate exact timestamps.

5. Build hypothesis and branch by regime
- Define one primary hypothesis and one invalidation criterion.
- Branch logic:
  - If chain liveness is stable and mempool pressure normal: proceed with plan drafting.
  - If mempool pressure spikes or node health degrades: reduce size or defer execution.
  - If data conflicts across sources: mark as unresolved and block trade until reconciled.

6. Convert analysis into a risk-bounded trading plan
- Required fields:
  - setup description
  - entry condition
  - stop condition
  - exit targets
  - max loss in EVR and in percent of account
  - position sizing method
- Use a simple default sizing policy:
  - `low`: risk <= 0.5% per trade
  - `medium`: risk <= 1.0% per trade
  - `high`: risk <= 1.5% per trade
- Add operational safeguards:
  - cooldown after consecutive losses
  - daily stop-trading threshold
  - no averaging down unless explicitly justified

7. Validate against project integration patterns
- Prefer existing RPC wrappers and conventions in:
  - `Tome/API/rpc.py`
  - `Tome/Wallet/rpc.py`
  - `Tome/Explorer/rpc.py`
- Check existing command references in:
  - `.github/docs/commands-cheatsheet.md`
  - `scripts/verify_rpc_cheatsheet.py`
- Reuse these patterns before adding new RPC plumbing.
- If RPC reliability is in question, run local-node backup validation:
  - `python .github/skills/evrmore-market-research-rpc/scripts/local_rpc_backup_probe.py`
  - then follow [project-rpc-implementation-backup.md](./references/project-rpc-implementation-backup.md)

8. Produce final output artifacts
- Output 1: concise thesis summary.
- Output 2: evidence table (source, timestamp, metric, interpretation).
- Output 3: actionable plan with hard risk bounds.
- Output 4: fail conditions and monitoring checklist for the next session.
- Start from: [trading-session-report-template.md](./assets/trading-session-report-template.md)

9. If goal is dex-architecture, produce an on-chain-only DEX blueprint
- Define strict scope:
  - spot exchange only
  - no wrapped assets
  - no off-chain custody
  - no synthetic settlement assets
- Define asset model and pair rules:
  - all base and quote instruments must be native EVRMore assets
  - pair registry must validate asset existence via `getassetdata`
  - pair lifecycle must include tradable, paused, delisted states
- Define order and settlement model:
  - prefer fully on-chain atomic swap style settlement for matched intents
  - enforce UTXO-backed balance checks before order acceptance
  - define timeout and cancel semantics for partially completed swap flows
- Define anti-fragility and abuse controls:
  - min order sizes and precision checks from chain rules
  - replay prevention and idempotent order identifiers
  - max open orders, max notional per address, and emergency market pause
- Define implementation handoff artifacts:
  - API contracts
  - state machine for order and settlement lifecycle
  - threat model and failure-mode matrix
  - phased rollout plan (testnet -> limited mainnet -> full mainnet)
- Start from:
  - [dex-architecture-template.md](./assets/dex-architecture-template.md)
  - [dex-threat-model-template.md](./assets/dex-threat-model-template.md)
  - [dex-rollout-checklist.md](./assets/dex-rollout-checklist.md)

## Decision Points
- Endpoint routing:
  - If `POST /` fails with `Cannot POST /`, retry on `/rpc`.
- Endpoint instability:
  - If timeout/error rate exceeds threshold, switch to alternate network endpoint or pause.
- Whitelist restriction:
  - If endpoint is reachable but returns whitelist restrictions for required methods, use local node RPC for full telemetry and settlement-critical checks.
- Network mismatch:
  - If `chain` is not expected (`main` vs `test`), abort data collection and correct endpoint.
- Evidence conflict:
  - If public claims cannot be backed by on-chain data, downgrade confidence and reduce risk.
- DEX scope drift:
  - If any requirement introduces wrapped or off-chain settlement assets, reject and redesign to preserve on-chain-only settlement.

## Completion Criteria
- Source coverage:
  - official EVRMore pages reviewed and relevant sublinks triaged
- RPC validation:
  - successful health checks on requested network(s)
- Evidence quality:
  - each trading claim tied to at least one timestamped data point
- Risk quality:
  - explicit max loss, position size rule, and stop-trading criteria defined
- Reproducibility:
  - commands and assumptions documented so another operator can rerun them
- DEX integrity (when goal is dex-architecture):
  - all listed trading pairs are native on-chain assets
  - settlement flow is defined without custodial or wrapped-asset dependencies
  - failure handling, timeout behavior, and recovery paths are explicitly specified

## Suggested Prompt Patterns
- `/evrmore-market-research-rpc goal=market-scan network=both horizon=intraday risk=low`
- `/evrmore-market-research-rpc goal=trade-plan network=mainnet horizon=intraday risk=medium`
- `/evrmore-market-research-rpc goal=rpc-health network=testnet horizon=swing risk=low`
- `/evrmore-market-research-rpc goal=dex-architecture network=both horizon=swing risk=low`
