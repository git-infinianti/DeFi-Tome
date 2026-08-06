---
name: evrmore-engineer
description: "General EVRMore engineering workflow for wallet, RPC, chain-data, asset, and on-chain DEX work, with market research and trading analysis as optional evidence-gathering modes. Use when building, debugging, validating, or planning EVRMore-related systems."
argument-hint: "goal=<wallet-ops|rpc-health|rpc-implementation|market-scan|trade-plan|dex-architecture> network=<mainnet|testnet|both> horizon=<intraday|swing> risk=<low|medium|high>"
user-invocable: true
---

# EVRMore Engineer

Build a repeatable EVRMore engineering workflow by combining:
- project implementation context
- wallet and RPC validation
- source-document review when external claims matter
- market analysis when it helps an engineering or operational decision
- explicit risk controls and validation gates

This skill is for engineering, analysis, and planning across EVRMore surfaces, including:
- wallet flows
- RPC integrations
- asset and address telemetry
- trading and market research
- on-chain DEX architecture

Use market research as an additional capability, not the default identity.

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
- You are implementing or debugging EVRMore wallet, address, balance, UTXO, transfer, or signing flows.
- You need to validate EVRMore RPC behavior, endpoint health, network alignment, or method availability.
- You need a structured EVRMore research pass before taking a trade or shaping a product decision.
- You want reproducible notes and commands that can be audited later.
- You want to design a DEX flow that settles exclusively with native on-chain EVRMore assets.

## Inputs
- `goal`: `wallet-ops`, `rpc-health`, `rpc-implementation`, `market-scan`, `trade-plan`, or `dex-architecture`
- `network`: `mainnet`, `testnet`, or `both`
- `horizon`: `intraday` or `swing` when market analysis is part of the task
- `risk`: `low`, `medium`, `high` when market analysis or trading plans are part of the task
- Optional watchlist pairs, target addresses/assets, and session window

## Required Public Endpoints
Use these as first choice endpoints:
- `https://evr-rpc-mainnet.evrmorecoin.org/rpc`
- `https://evr-rpc-testnet.evrmorecoin.org/rpc`

Important:
- The host root (`/`) returns `Cannot POST /`.
- JSON-RPC is served at `/rpc`.

## Procedure

1. Define mission and constraints
- State the objective in one sentence: implementation, debugging, discovery, setup, or execution plan.
- Identify the primary EVRMore surface first:
  - wallet operations
  - RPC integration or health
  - chain telemetry and evidence gathering
  - market research and trading plan
  - DEX architecture
- Set hard constraints first:
  - max operational risk
  - max daily drawdown when trading is in scope
  - max concurrent positions when trading is in scope
  - no-go conditions such as low liquidity, unstable RPC, abnormal spreads, or incomplete wallet-state validation
- Pick analysis horizon and network when relevant.

2. Validate project integration patterns first
- Prefer existing RPC wrappers and conventions in:
  - `Tome/API/rpc.py`
  - `Tome/Wallet/rpc.py`
  - `Tome/Explorer/rpc.py`
- Check existing command references in:
  - `.github/docs/commands-cheatsheet.md`
  - `scripts/verify_rpc_cheatsheet.py`
- Reuse these patterns before adding new RPC plumbing.

3. Probe RPC health and capability
- Run a minimal health check on target network:
  - `getblockchaininfo`
  - `getbestblockhash`
  - `getmempoolinfo`
- Confirm the chain (`main` or `test`) matches requested scope.
- Retrieve command discovery via `help` when uncertain about method names.
- Prefer script-based checks for repeatability:
  - `python .github/skills/evrmore-engineer/scripts/rpc_health_check.py --network both`
  - if local CA trust is missing, temporary fallback:
    - `python .github/skills/evrmore-engineer/scripts/rpc_health_check.py --network both --insecure`
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

4. Branch by engineering goal
- `wallet-ops`:
  - validate address, asset, balance, and UTXO data paths
  - confirm signing and broadcast flows use the correct trust boundary
  - block changes that rely only on public RPC for settlement-critical operations
- `rpc-implementation`:
  - confirm wrapper behavior, timeout handling, and fallback rules
  - document method coverage and restricted-access behavior
  - preserve existing interfaces where possible
- `market-scan` or `trade-plan`:
  - build the EVRMore knowledge map from official and third-party sources
  - pull timestamped on-chain signals and connect them to one explicit hypothesis
  - convert analysis into a risk-bounded trading plan
- `dex-architecture`:
  - define spot-only, on-chain-native settlement rules
  - validate assets and pair lifecycle requirements with chain data
  - define timeout, cancel, abuse-control, and recovery behavior

5. Build evidence
- For wallet and RPC tasks, gather the minimum chain data needed to verify balances, UTXOs, assets, or network state.
- For market tasks, collect block cadence, liveness, mempool pressure, asset telemetry, and any monitored address signals.
- Timebox data pulls and annotate exact timestamps.

6. Build hypothesis and invalidation
- Define one primary hypothesis and one invalidation criterion.
- Example branches:
  - if chain liveness is stable and mempool pressure normal, proceed with implementation or plan drafting
  - if mempool pressure spikes or node health degrades, reduce scope or defer execution
  - if public RPC lacks required methods, switch to local node RPC for full telemetry or state-changing work
  - if data conflicts across sources, mark as unresolved and block action until reconciled

7. Apply domain-specific safeguards
- source-document review
- For wallet and RPC changes:
  - treat local node RPC as required for signing, broadcasting, and UTXO-critical decision paths
  - keep interfaces stable unless the change is intentional and documented
  - make fallback and restricted-access behavior explicit
- For market and trading changes:
  - use simple default sizing policy:
    - `low`: risk <= 0.5% per trade
    - `medium`: risk <= 1.0% per trade
    - `high`: risk <= 1.5% per trade
  - add cooldown and stop-trading thresholds
- For DEX design:
  - reject wrapped-asset or off-chain settlement scope drift
  - require idempotent order identifiers, timeout behavior, and emergency pause controls

8. Build optional EVRMore knowledge map when external claims matter
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

9. Pull market-relevant on-chain signals when market analysis is in scope
- Collect block cadence and liveness:
  - `blocks`, `headers`, `mediantime`, `verificationprogress`
- Collect congestion and execution pressure:
  - `getmempoolinfo` (`size`, `bytes`, fee-related fields when available)
- Collect asset and address signals relevant to EVR trading thesis:
  - `listassets` for discovery windows
  - `getassetdata` for specific assets
  - `getaddressbalance` or `getaddressutxos` for monitored addresses
- Timebox data pulls and annotate exact timestamps.

10. Convert analysis into a risk-bounded trading plan when trading is in scope
- Required fields:
  - setup description
  - entry condition
  - stop condition
  - exit targets
  - max loss in EVR and in percent of account
  - position sizing method
- Add operational safeguards:
  - cooldown after consecutive losses
  - daily stop-trading threshold
  - no averaging down unless explicitly justified

11. Validate backup path when RPC reliability is in question
- Run local-node backup validation:
  - `python .github/skills/evrmore-engineer/scripts/local_rpc_backup_probe.py`
  - then follow [project-rpc-implementation-backup.md](./references/project-rpc-implementation-backup.md)

12. Produce final output artifacts
- For engineering tasks:
  - objective summary
  - verified facts and commands run
  - implementation or debugging recommendation
  - failure conditions, fallback path, and next validation step
- For market tasks:
  - concise thesis summary
  - evidence table (source, timestamp, metric, interpretation)
  - actionable plan with hard risk bounds
  - fail conditions and monitoring checklist for the next session
- Start from [trading-session-report-template.md](./assets/trading-session-report-template.md) when the task is market-focused.

13. If goal is `dex-architecture`, produce an on-chain-only DEX blueprint
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
  - If endpoint is reachable but returns whitelist restrictions for required methods, use local node RPC for full telemetry, wallet-critical checks, and settlement-critical checks.
- Network mismatch:
  - If `chain` is not expected (`main` vs `test`), abort data collection and correct endpoint.
- Evidence conflict:
  - If public claims cannot be backed by on-chain data, downgrade confidence and reduce risk.
- DEX scope drift:
  - If any requirement introduces wrapped or off-chain settlement assets, reject and redesign to preserve on-chain-only settlement.

## Completion Criteria
- Source coverage:
  - official EVRMore pages reviewed and relevant sublinks triaged when external claims matter
- RPC validation:
  - successful health checks on requested network(s)
- Evidence quality:
  - each engineering or trading claim tied to at least one verified fact, command, or timestamped data point
- Risk quality:
  - explicit operational constraints defined, plus max loss and stop-trading criteria when trading is in scope
- Reproducibility:
  - commands and assumptions documented so another operator can rerun them
- DEX integrity (when goal is dex-architecture):
  - all listed trading pairs are native on-chain assets
  - settlement flow is defined without custodial or wrapped-asset dependencies
  - failure handling, timeout behavior, and recovery paths are explicitly specified

## Suggested Prompt Patterns
- `/evrmore-engineer goal=wallet-ops network=mainnet`
- `/evrmore-engineer goal=rpc-implementation network=both`
- `/evrmore-engineer goal=market-scan network=both horizon=intraday risk=low`
- `/evrmore-engineer goal=trade-plan network=mainnet horizon=intraday risk=medium`
- `/evrmore-engineer goal=rpc-health network=testnet horizon=swing risk=low`
- `/evrmore-engineer goal=dex-architecture network=both horizon=swing risk=low`
