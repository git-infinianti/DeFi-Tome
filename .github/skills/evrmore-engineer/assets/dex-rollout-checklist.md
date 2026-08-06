# EVRMore On-Chain-Only DEX Rollout Checklist

## Phase 0: Pre-Implementation
- [ ] Scope documented: spot only, on-chain assets only
- [ ] Architecture template completed
- [ ] Threat model completed
- [ ] Failure-mode matrix completed

## Phase 1: Testnet Functional Validation
- [ ] Pair registry validates assets via getassetdata
- [ ] Order state machine happy path tested
- [ ] Cancel, timeout, and recovery paths tested
- [ ] UTXO conflict handling tested
- [ ] Per-address limits enforced
- [ ] Structured logs and metrics emitted

Go/No-Go for Phase 2:
- [ ] 0 critical unresolved defects
- [ ] >= 95% integration-test pass rate
- [ ] No unreconciled settlement records after test runs

## Phase 2: Limited Mainnet Launch
- [ ] Launch allowlisted markets only
- [ ] Reduced order-size caps enabled
- [ ] Emergency pause controls validated in production
- [ ] Alerts for failure and saturation configured
- [ ] Operator runbook reviewed and approved

Go/No-Go for Phase 3:
- [ ] Stability window met (define duration)
- [ ] No severity-1 incidents in window
- [ ] Settlement reconciliation complete for all sample sessions

## Phase 3: Full Mainnet Release
- [ ] Market expansion plan approved
- [ ] Risk limits tuned using observed production behavior
- [ ] Post-incident and post-session review cadence active
- [ ] Security and dependency review current

## Rollback Triggers
- [ ] Repeated settlement failures above threshold
- [ ] Data integrity drift between order and settlement stores
- [ ] Sustained endpoint instability
- [ ] Active exploitation indicators

## Emergency Actions
- [ ] Pause new orders
- [ ] Cancel eligible open orders
- [ ] Preserve audit logs and evidence
- [ ] Trigger incident communication plan
