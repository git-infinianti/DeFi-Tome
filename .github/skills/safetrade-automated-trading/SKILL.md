---
name: safetrade-automated-trading
description: "Design and implement SafeTrade automated trading bots. Use when building strategy logic, websocket market data handlers, signed REST execution, order lifecycle management, and risk controls for SafeTrade markets."
argument-hint: "strategy=<market-making|momentum|mean-reversion> market=<symbol> mode=<paper|live> profile=<conservative|balanced|aggressive>"
user-invocable: true
---

# SafeTrade Automated Trading

Build robust, testable automated trading systems for SafeTrade using REST + WebSocket flows and explicit risk management.

This skill is Python-first and should default to Python implementations unless explicitly asked for language-agnostic guidance.

## When To Use
- You need a full trading bot workflow, not a single API call.
- You are implementing a strategy engine (market making, momentum, mean reversion).
- You need safe execution behavior with cancel/retry/fallback logic.
- You want a go-live checklist with recommended (not mandatory) gates.

## Inputs
- Strategy archetype: `market-making`, `momentum`, or `mean-reversion`
- Target market(s): e.g. `btcusdt`, `qubicusdt`
- Trading mode: `paper` or `live`
- Risk profile preset: `conservative`, `balanced`, or `aggressive` (optional)
- Risk budget: max position, max notional, max daily loss, max open orders
- Latency and uptime goals

## Risk Preset Defaults
Use these as starting defaults, then override as needed per market liquidity and account size.

| Preset | Max Position / Market | Max Notional / Market | Max Daily Loss | Max Open Orders / Market | Max Slippage (market/stop) | Quote TTL (market-making) |
|---|---:|---:|---:|---:|---:|---:|
| conservative | 2% equity | 5% equity | 1.0% equity | 2 | 0.20% | 15s |
| balanced | 5% equity | 12% equity | 2.0% equity | 4 | 0.40% | 10s |
| aggressive | 10% equity | 20% equity | 3.5% equity | 6 | 0.70% | 6s |

Preset-specific order throttles:
- `conservative`: max 6 new orders/minute/market, circuit-break after 3 consecutive rejects.
- `balanced`: max 12 new orders/minute/market, circuit-break after 5 consecutive rejects.
- `aggressive`: max 20 new orders/minute/market, circuit-break after 7 consecutive rejects.

## Procedure

1. Define the mandate and operating envelope
- Specify objective: spread capture, trend following, or reversion to mean.
- Define non-negotiable limits before any code:
  - Max position per market
  - Max notional exposure
  - Max daily drawdown
  - Max open orders
  - Kill-switch conditions
- Choose operating mode:
  - `paper`: no live order placement
  - `live`: signed requests + private stream required

2. Validate exchange connectivity and auth
- Base URL: `https://safe.trade/api/v2`
- Verify auth by calling member endpoint first: `GET /trade/account/members/me`
- Use signed headers for private actions:
  - `X-Auth-Apikey`
  - `X-Auth-Nonce`
  - `X-Auth-Signature`
- Signature pattern from reference client: HMAC-SHA256 over `nonce + api_key` using `api_secret`.

3. Pull market microstructure constraints
- Query `GET /trade/public/markets` and cache per market:
  - `min_amount`, `min_price`, `amount_precision`, `price_precision`, `state`
- Query `GET /trade/public/trading_fees` for maker/taker assumptions.
- Build validation helpers that round/clip order params to exchange precision.

4. Build data ingestion layer
- REST snapshots for initialization:
  - `GET /trade/public/tickers`
  - `GET /trade/public/markets/{id}/depth`
  - `GET /trade/public/markets/{id}/trades`
- WebSocket live streams:
  - Public: `global.tickers`, `<market>.depth`, `<market>.trades`
  - Private: `order`, `trade`, `balance`
- Implement reconnect + resubscribe policy with exponential backoff and jitter.

5. Select strategy branch
- If `strategy=market-making`:
  - Quote both sides around microprice/mid.
  - Skew quotes by inventory and volatility.
  - Cancel stale quotes after timeout or adverse move.
- If `strategy=momentum`:
  - Derive trend from rolling returns, volume, and breakout confirmation.
  - Use pullback or stop entry with strict slippage caps.
- If `strategy=mean-reversion`:
  - Use z-score of spread/price deviation with volatility filter.
  - Enter only when liquidity and spread quality exceed thresholds.

6. Convert signals into executable intents
- Normalize each signal into an intent object:
  - `market`, `side`, `order_type`, `amount`, `price`, `ttl_ms`, `reason`
- Pass all intents through risk checks before sending.
- Prefer deterministic behavior: same inputs should yield same intents.

7. Add the risk firewall (hard gate)
- Start from preset limits when provided, then override with user-specific limits:
  - `conservative`: lower max position/notional, tighter drawdown and slippage caps
  - `balanced`: moderate limits and standard throttles
  - `aggressive`: larger limits with stricter monitoring and faster circuit breaks
- Pre-trade checks:
  - Position limit
  - Notional limit
  - Daily loss limit
  - Order frequency limit
  - Market state is tradable
- In-trade controls:
  - Max slippage
  - Max time-in-book for passive quotes
  - Circuit breaker on repeated rejects/errors
- Post-trade controls:
  - Update realized/unrealized PnL
  - Recompute available risk budget
  - Trigger de-risk flow when thresholds are crossed

8. Implement order lifecycle manager
- Use REST endpoints for execution:
  - `POST /trade/market/orders` create
  - `GET /trade/market/orders` list/open-state sync
  - `GET /trade/market/orders/{id}` reconcile status
  - `POST /trade/market/orders/{id}/cancel` cancel
- Maintain local order state machine:
  - `new -> acknowledged -> partially_filled -> filled`
  - `new -> rejected`
  - `new/acknowledged/partially_filled -> cancel_pending -> canceled`
- Reconcile local state with private stream events and periodic REST snapshots.

9. Test in paper mode, then stage to live
- Paper simulation:
  - Run strategy with live/public data and mocked execution fills.
  - Validate fill assumptions against observed spread/depth.
- Staging:
  - Trade minimal size.
  - Limit concurrent markets.
  - Enable kill switch and aggressive alerting.

Recommended light go-live gates:
- Paper run duration: at least 24 hours.
- Minimum signal count: at least 50 generated intents.
- Reject rate: under 5% during paper/staging.
- Reconciliation drift: 0 unreconciled open orders at session end.
- Drawdown check: stays within configured daily loss limit.

10. Observe and operate
- Emit structured logs for decisions and executions.
- Track core metrics:
  - Fill rate
  - Reject rate
  - Cancel-to-fill ratio
  - Realized PnL
  - Drawdown
  - Stream disconnect count
- Add runbooks for common failures (auth errors, websocket churn, stale order state).

## Decision Points and Branching
- Auth failure (`401`): refresh nonce/signature path and block trading until green healthcheck.
- Validation failure (`422`): adjust precision/minimum filters and retry once; otherwise drop intent.
- Repeated server errors (`500`): trip circuit breaker and move to safe mode.
- WebSocket lag/disconnect: pause new entries, keep cancel safety path alive, resume after sync.
- Excess drawdown: hard stop new orders, cancel working orders, reduce inventory.

## Completion Criteria (Quality Gates)
A bot should strongly prefer passing these checks before live mode:
- Connectivity: stable public/private websocket sessions with auto-recovery.
- Execution: idempotent create/cancel behavior and consistent order reconciliation.
- Safety: all risk limits enforced in pre-trade and runtime paths.
- Correctness: no precision/min-amount violations in submitted orders.
- Reliability: soak test passes for at least one sustained session without unreconciled orders.
- Observability: metrics and logs support post-trade attribution per strategy decision.

If business constraints require earlier live rollout, enforce reduced risk mode first (smaller size, fewer markets, stricter kill-switch thresholds).

## SafeTrade-Specific References
- API map and endpoint checklist: [SafeTrade API Cheat Sheet](./references/safetrade-api-cheat-sheet.md)
- Implementation patterns from example client: [Example Client Notes](./references/example-client-notes.md)
- Equity-based limit calculator prompt: [SafeTrade Risk Cap Calculator](../../prompts/safetrade-risk-cap-calculator.prompt.md)
- JSON to Python settings prompt: [SafeTrade Config To Python](../../prompts/safetrade-config-to-python.prompt.md)
- Python config test prompt: [SafeTrade Config Pytest Generator](../../prompts/safetrade-config-pytest.prompt.md)
- Paper-to-live checklist prompt: [SafeTrade Paper To Live Runbook](../../prompts/safetrade-paper-to-live-runbook.prompt.md)
- Incident postmortem prompt: [SafeTrade Incident Postmortem](../../prompts/safetrade-incident-postmortem.prompt.md)
- Weekly operations review prompt: [SafeTrade Weekly Ops Report](../../prompts/safetrade-weekly-ops-report.prompt.md)
- Daily readiness prompt: [SafeTrade Daily Preflight](../../prompts/safetrade-daily-preflight.prompt.md)
- Live triage prompt: [SafeTrade Live Alert Triage](../../prompts/safetrade-live-alert-triage.prompt.md)
- Reconciliation audit prompt: [SafeTrade Order Reconciliation Audit](../../prompts/safetrade-order-reconciliation-audit.prompt.md)
- Strategy tuning prompt: [SafeTrade Strategy Parameter Tuning](../../prompts/safetrade-strategy-parameter-tuning.prompt.md)
- Monthly review prompt: [SafeTrade Monthly Strategy Review](../../prompts/safetrade-monthly-strategy-review.prompt.md)
- Backtest validation prompt: [SafeTrade Backtest Forward-Test Review](../../prompts/safetrade-backtest-forwardtest-review.prompt.md)

## Suggested Prompt Patterns
- `/safetrade-automated-trading strategy=market-making market=qubicusdt mode=paper profile=conservative`
- `/safetrade-automated-trading strategy=momentum market=btcusdt mode=paper profile=balanced`
- `/safetrade-automated-trading strategy=mean-reversion market=ethusdt mode=live profile=aggressive`
- `/SafeTrade Risk Cap Calculator equity=10000 currency=USDT profile=balanced markets=btcusdt,ethusdt mode=paper`
- `/SafeTrade Config To Python module=bot_config.py env_prefix=BOT_`
- `/SafeTrade Config Pytest Generator module=bot_config.py test_file=tests/test_bot_config.py`
- `/SafeTrade Paper To Live Runbook profile=balanced mode=live markets=btcusdt,ethusdt`
- `/SafeTrade Incident Postmortem severity=sev2 strategy=market-making markets=btcusdt,ethusdt`
- `/SafeTrade Weekly Ops Report week=2026-W31 strategies=market-making,momentum markets=btcusdt,ethusdt`
- `/SafeTrade Daily Preflight mode=live profile=balanced markets=btcusdt,ethusdt`
- `/SafeTrade Live Alert Triage alert_type=execution severity=sev2`
- `/SafeTrade Order Reconciliation Audit window=last_24h mode=live markets=btcusdt,ethusdt`
- `/SafeTrade Strategy Parameter Tuning strategy=momentum profile=balanced markets=btcusdt`
- `/SafeTrade Monthly Strategy Review month=2026-08 strategies=market-making,momentum profiles=conservative,balanced markets=btcusdt,ethusdt`
- `/SafeTrade Backtest Forward-Test Review strategy=mean-reversion next_mode=paper markets=ethusdt`
