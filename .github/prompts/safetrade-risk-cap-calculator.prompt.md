---
description: "Compute concrete SafeTrade bot risk caps from account equity and profile, with optional custom overrides and final ready-to-use config."
name: "SafeTrade Risk Cap Calculator"
argument-hint: "equity=<amount> currency=<USDT> profile=<conservative|balanced|aggressive> markets=<csv> mode=<paper|live>"
agent: "agent"
---

Compute concrete SafeTrade trading risk caps from the inputs and return a ready-to-use configuration.

## Inputs
- Equity amount (required): numeric account equity in quote currency.
- Equity currency (default USDT).
- Risk profile: conservative, balanced, or aggressive.
- Markets: comma-separated market list such as btcusdt,ethusdt.
- Mode: paper or live.
- Optional overrides:
  - max_position_pct_per_market
  - max_notional_pct_per_market
  - max_daily_loss_pct
  - max_open_orders_per_market
  - max_slippage_pct
  - quote_ttl_seconds
  - max_new_orders_per_minute_per_market
  - reject_circuit_breaker_count

If required inputs are missing, ask concise follow-up questions and stop.

## Preset Defaults
Use these profile defaults unless overridden.

- conservative
  - max_position_pct_per_market: 2.0
  - max_notional_pct_per_market: 5.0
  - max_daily_loss_pct: 1.0
  - max_open_orders_per_market: 2
  - max_slippage_pct: 0.20
  - quote_ttl_seconds: 15
  - max_new_orders_per_minute_per_market: 6
  - reject_circuit_breaker_count: 3

- balanced
  - max_position_pct_per_market: 5.0
  - max_notional_pct_per_market: 12.0
  - max_daily_loss_pct: 2.0
  - max_open_orders_per_market: 4
  - max_slippage_pct: 0.40
  - quote_ttl_seconds: 10
  - max_new_orders_per_minute_per_market: 12
  - reject_circuit_breaker_count: 5

- aggressive
  - max_position_pct_per_market: 10.0
  - max_notional_pct_per_market: 20.0
  - max_daily_loss_pct: 3.5
  - max_open_orders_per_market: 6
  - max_slippage_pct: 0.70
  - quote_ttl_seconds: 6
  - max_new_orders_per_minute_per_market: 20
  - reject_circuit_breaker_count: 7

## Computation Rules
- max_position_value_per_market = equity * max_position_pct_per_market / 100
- max_notional_value_per_market = equity * max_notional_pct_per_market / 100
- max_daily_loss_value = equity * max_daily_loss_pct / 100
- Round currency values to 2 decimals unless the user requests different precision.
- Keep percentages in percent units (not decimals) in the report.
- Apply overrides after preset selection.

## Light Go-Live Gate Guidance
Include recommended gates in the result:
- paper_runtime_hours_min: 24
- intents_min: 50
- reject_rate_pct_max: 5
- unreconciled_open_orders_end_of_session: 0
- drawdown_within_limit: required

## Output Format
Return exactly these sections in this order.

1) Summary
- equity, currency, profile, mode, markets

2) Effective Limits Table
- show effective percent limits and absolute currency limits

3) Per-Market Caps
- one row per market with position value cap and notional value cap

4) Bot Config JSON
Provide valid JSON with this shape:

{
  "profile": "balanced",
  "mode": "paper",
  "equity": 10000,
  "currency": "USDT",
  "markets": ["btcusdt", "ethusdt"],
  "limits": {
    "max_position_pct_per_market": 5.0,
    "max_position_value_per_market": 500.0,
    "max_notional_pct_per_market": 12.0,
    "max_notional_value_per_market": 1200.0,
    "max_daily_loss_pct": 2.0,
    "max_daily_loss_value": 200.0,
    "max_open_orders_per_market": 4,
    "max_slippage_pct": 0.4,
    "quote_ttl_seconds": 10,
    "max_new_orders_per_minute_per_market": 12,
    "reject_circuit_breaker_count": 5
  },
  "go_live_gates": {
    "paper_runtime_hours_min": 24,
    "intents_min": 50,
    "reject_rate_pct_max": 5,
    "unreconciled_open_orders_end_of_session": 0,
    "drawdown_within_limit": true
  }
}

5) Notes
- list any overrides applied
- list assumptions
- include one short warning if mode is live
