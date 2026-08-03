---
description: "Generate a SafeTrade trading-incident postmortem from logs, metrics, and timeline data with root cause, corrective actions, and prevention plan."
name: "SafeTrade Incident Postmortem"
argument-hint: "severity=<sev1|sev2|sev3> strategy=<market-making|momentum|mean-reversion> markets=<csv>"
agent: "agent"
---

Produce a practical, blameless postmortem for a SafeTrade bot incident.

## Inputs
- Incident summary
- Severity (`sev1`, `sev2`, `sev3`)
- Strategy and markets involved
- Timeline events with timestamps
- Operational metrics around the incident window:
  - reject_rate_pct
  - cancel_to_fill_ratio
  - websocket_disconnect_count
  - unreconciled_open_orders
  - realized_pnl
  - max_drawdown_pct
- Relevant logs or excerpts
- Mitigations already applied (if any)

If required incident data is missing, ask concise follow-up questions and stop.

## Analysis Goals
1. Build a clear timeline of what happened.
2. Separate symptoms from root causes.
3. Identify contributing factors (code, config, market conditions, ops process).
4. Quantify impact (PnL, downtime, order errors, safety limit breaches).
5. Produce prioritized corrective actions with owners and due dates.
6. Add prevention checks to catch recurrence earlier.

## Safety and Quality Rules
- Use a blameless style focused on systems and process.
- Never include API keys, secrets, or private credentials.
- If unreconciled orders > 0, include a high-severity reconciliation warning.
- If drawdown exceeds configured max daily loss, mark risk controls as failed and require remediation before live resume.
- If disconnect spikes and reject rate spikes coincide, highlight transport/execution coupling risk.

## Output Format
Return sections in this exact order:
1) Executive Summary
2) Incident Scope and Impact
3) Timeline (UTC)
4) Root Cause Analysis
5) Contributing Factors
6) What Worked / What Failed
7) Corrective Actions (Prioritized)
8) Prevention and Monitoring Upgrades
9) Live Resume Criteria
10) Appendix (Key Metrics and Log Evidence)

## Corrective Actions Format
For each action include:
- id
- priority (`P0`, `P1`, `P2`)
- owner
- due_date
- action
- expected_outcome
- verification_method

## Optional Add-ons
If requested, also provide:
- A one-page stakeholder summary
- A Jira-ready action list table
- A follow-up review agenda for 7-day and 30-day checkpoints
