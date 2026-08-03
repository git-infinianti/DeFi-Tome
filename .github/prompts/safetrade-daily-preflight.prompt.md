---
description: "Run a SafeTrade daily preflight that validates readiness before starting paper or live trading sessions."
name: "SafeTrade Daily Preflight"
argument-hint: "mode=<paper|live> profile=<conservative|balanced|aggressive> markets=<csv>"
agent: "agent"
---

Generate a concise preflight readiness report for a SafeTrade bot session.

## Inputs
- mode: paper or live
- profile
- markets list
- config limits summary (optional but recommended)
- latest system health signals (optional):
  - ws_disconnects_last_24h
  - api_error_rate_pct
  - unreconciled_orders_count
  - last_incident_age_hours

If key inputs are missing, ask concise follow-up questions and stop.

## Checks
1. Connectivity and auth
- private auth handshake path valid
- websocket public/private reachable

2. Market constraints freshness
- markets metadata not stale
- precision and minimum-size guards present

3. Risk controls
- max position/notional/drawdown limits loaded
- kill-switch path tested recently
- order throttle and reject breaker configured

4. State hygiene
- unreconciled open orders = 0
- pending cancel queue is empty
- last session shutdown was clean

5. Operational readiness
- alert routing configured
- on-call owner and escalation path known

## Decision Logic
- READY if all critical checks pass.
- READY-WITH-GUARDS if only non-critical checks fail.
- BLOCKED if any critical check fails.

Critical failures include:
- auth failure
- missing risk limits
- unreconciled orders > 0
- websocket private channel unavailable in live mode

## Output Format
Return sections in this exact order:
1) Session Summary
2) Check Results Table
3) Decision (READY | READY-WITH-GUARDS | BLOCKED)
4) Required Fixes Before Start
5) Optional Hardening Steps
