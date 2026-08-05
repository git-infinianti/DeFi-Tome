# EVRMore DEX Threat Model Template

## System Context
- Components in scope:
- Trust boundaries:
- External dependencies:

## Security Objectives
- Preserve on-chain-only settlement integrity
- Prevent unauthorized fund movement
- Ensure deterministic order/settlement replay safety

## Threat Inventory
| Threat ID | Threat | Surface | Impact | Likelihood | Severity |
|---|---|---|---|---|---|
| T-001 | Replay of order intent | API/order transport | Double execution |  |  |
| T-002 | Settlement timeout abuse | Swap lifecycle | Locked funds |  |  |
| T-003 | Malformed asset pair injection | Pair registry | Invalid market state |  |  |
| T-004 | UTXO race condition | Balance/selection | Failed settlement |  |  |
| T-005 | DoS on matching or settlement path | Service endpoints | Service disruption |  |  |

## Controls And Mitigations
| Threat ID | Preventive Controls | Detective Controls | Recovery Controls |
|---|---|---|---|
| T-001 | Idempotency key, nonce rules | Duplicate intent alerts | Safe rollback path |
| T-002 | Strict expiry semantics | Timeout monitoring | Automated cancel and release |
| T-003 | Chain-backed validation via getassetdata | Pair audit logs | Immediate delist/pause |
| T-004 | Reservation + revalidation before settle | UTXO conflict metrics | Retry or cancel with reconciliation |
| T-005 | Rate limits and per-address quotas | Saturation alerts | Traffic shedding and pause mode |

## Residual Risks
- 

## Validation Plan
- Unit tests:
- Integration tests:
- Chaos/failure drills:
