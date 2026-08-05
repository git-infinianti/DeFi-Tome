# EVRMore On-Chain-Only DEX Architecture Template

## 1. Scope And Non-Negotiables
- Product scope:
- Supported market type: spot only
- Settlement rule: on-chain assets only
- Prohibited patterns:
  - wrapped assets
  - custodial omnibus balances
  - off-chain synthetic settlement

## 2. Pair Registry Model
- Pair identifier convention:
- Base asset:
- Quote asset:
- Asset validation RPC checks:
  - getassetdata(base)
  - getassetdata(quote)
- Pair lifecycle states:
  - tradable
  - paused
  - delisted

## 3. Order Model
- Order types:
- Required fields:
  - order_id
  - market
  - side
  - price
  - amount
  - created_at
  - expires_at
- Risk fields:
  - max_notional
  - per-address open-order cap

## 4. Settlement State Machine
- states:
  - created
  - reserved
  - matched
  - settlement_pending
  - settled
  - canceled
  - expired
  - failed
- transitions and failure paths:

## 5. Pre-Trade Validation
- Address format and network checks:
- UTXO and spendability checks:
- Asset precision and min-size checks:
- Anti-replay/idempotency checks:

## 6. Runtime Risk Controls
- Max open orders per address:
- Max notional per address/market:
- Market-wide circuit-breakers:
- Emergency pause and cancel-all controls:

## 7. Security And Abuse Controls
- Threat categories:
- Relevant attack surfaces:
- Control mapping:

## 8. Observability
- Core metrics:
- Alert thresholds:
- Structured logs and correlation keys:

## 9. Rollout Plan
- testnet dry run criteria:
- limited mainnet launch criteria:
- full launch criteria:
- rollback criteria:

## 10. Open Questions
- 
