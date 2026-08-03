---
description: "Generate a SafeTrade paper-to-live preflight checklist and operational runbook from bot config and recent paper-trading metrics."
name: "SafeTrade Paper To Live Runbook"
argument-hint: "profile=<conservative|balanced|aggressive> mode=<paper|live> markets=<csv>"
agent: "agent"
---

Create a practical paper-to-live runbook for a SafeTrade bot.

## Inputs
- Bot config JSON (recommended)
- Profile: conservative, balanced, or aggressive
- Markets list
- Last paper-trading metrics, if available:
  - paper_runtime_hours
  - intents_count
  - reject_rate_pct
  - unreconciled_open_orders_end_of_session
  - max_drawdown_pct
  - disconnect_count

If metrics are missing, produce a checklist with placeholders and call out missing data.

## Objective
Return a go/no-go assessment with concrete actions and rollback procedures.

## Gate Policy (Light, Recommended)
Evaluate and report pass/fail for each gate:
- paper_runtime_hours >= 24
- intents_count >= 50
- reject_rate_pct < 5
- unreconciled_open_orders_end_of_session == 0
- max_drawdown_pct <= configured max_daily_loss_pct
- websocket reconnect and resubscribe behavior verified

## What To Produce
1. Preflight checklist
- Auth check flow
- Market metadata freshness
- Precision and minimum-size guards
- Risk limit enforcement
- Order lifecycle reconciliation
- Alert routing and kill-switch test

2. Go/No-Go decision
- Decision: GO, GO-WITH-GUARDS, or NO-GO
- Top 3 risks
- Required mitigations

3. Live rollout plan
- Initial order size multiplier
- Max concurrent markets at launch
- Monitoring cadence for first 60 minutes
- Escalation owner and response windows

4. Rollback runbook
- Immediate actions on trigger
- Cancel-all flow
- New-order lockout
- State reconciliation steps
- Resume criteria

5. Post-launch review template
- KPI summary
- Incident timeline
- Corrective actions

## Safety Rules
- If mode is live and 2 or more gates fail, default to NO-GO.
- If reject_rate_pct >= 10 or unreconciled orders > 0, include an explicit high-severity warning.
- Never include API keys or secrets in output.

## Output Format
Return sections in this exact order:
1) Summary
2) Gate Evaluation Table
3) Preflight Checklist
4) Go/No-Go Decision
5) Rollout Plan
6) Rollback Runbook
7) Post-Launch Review Template
