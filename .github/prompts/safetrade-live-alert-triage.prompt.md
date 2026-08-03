---
description: "Triage live SafeTrade alerts into severity, likely root cause, immediate actions, and escalation path."
name: "SafeTrade Live Alert Triage"
argument-hint: "alert_type=<execution|risk|reconciliation|connectivity> severity=<sev1|sev2|sev3>"
agent: "agent"
---

Triage a live trading alert and produce an operator-grade response plan.

## Inputs
- alert_type
- current severity
- affected strategies and markets
- latest metrics around alert window:
  - reject_rate_pct
  - cancel_to_fill_ratio
  - websocket_disconnect_count
  - unreconciled_orders_count
  - drawdown_pct
  - pnl_delta
- recent log snippets (optional)

If required details are missing, ask concise follow-up questions and stop.

## Triage Goals
1. Confirm or adjust severity level.
2. Identify likely failure domain:
- transport
- exchange/API
- strategy logic
- risk control
- state reconciliation

3. Provide immediate containment actions.
4. Define escalation and communication steps.
5. Define resume criteria.

## Safety Rules
- If unreconciled orders > 0, include immediate reconciliation action.
- If drawdown breaches daily limit, lock new orders and require manual re-enable.
- If reject_rate_pct >= 10, downgrade to safe mode and reduce order frequency.

## Output Format
Return sections in this exact order:
1) Alert Snapshot
2) Severity Assessment
3) Probable Root Cause Domains
4) Immediate Actions (0-5 min)
5) Stabilization Actions (5-30 min)
6) Escalation Plan
7) Resume Criteria
8) Post-Incident Follow-up Tasks
