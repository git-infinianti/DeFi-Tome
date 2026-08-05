---
description: "Use the evrmore-market-research-rpc skill whenever work involves EVRMore or wallet interactions, including RPC usage, address and UTXO flows, trading analysis, and on-chain DEX architecture decisions."
---

# EVRMore And Wallet Skill Routing

## Trigger Conditions
Use the evrmore-market-research-rpc skill whenever the request or edited files involve any of the following:
- EVRMore network behavior, chain data, RPC methods, or endpoint health
- Wallet operations such as addresses, balances, UTXOs, signatures, or transfers
- Trading or market-research workflows for EVRMore assets
- On-chain-only DEX design, settlement logic, or risk controls

## Required Workflow
1. Load the skill at .github/skills/evrmore-market-research-rpc/SKILL.md.
2. Follow the skill procedure, decision points, and completion criteria.
3. Prefer existing project RPC wrappers before introducing new RPC plumbing.
4. Use the skill assets and script when applicable:
- .github/skills/evrmore-market-research-rpc/scripts/rpc_health_check.py
- .github/skills/evrmore-market-research-rpc/scripts/local_rpc_backup_probe.py
- .github/skills/evrmore-market-research-rpc/assets/trading-session-report-template.md
- .github/skills/evrmore-market-research-rpc/assets/dex-architecture-template.md
- .github/skills/evrmore-market-research-rpc/assets/dex-threat-model-template.md
- .github/skills/evrmore-market-research-rpc/assets/dex-rollout-checklist.md
- .github/skills/evrmore-market-research-rpc/references/project-rpc-implementation-backup.md

## Quality Bar
- Outputs should be evidence-backed with reproducible commands or references.
- Risk and failure modes must be explicit for trading and DEX changes.
- If public RPC access is restricted, document constraints and use local node RPC for full checks.
- For RPC implementation incidents, follow the backup runbook and local probe before introducing new RPC plumbing.
