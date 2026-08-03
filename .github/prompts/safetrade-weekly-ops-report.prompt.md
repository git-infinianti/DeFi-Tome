---
description: "Generate a weekly SafeTrade trading operations report from strategy metrics, incidents, and risk data with KPIs, insights, and action plan."
name: "SafeTrade Weekly Ops Report"
argument-hint: "week=<YYYY-Www> strategies=<csv> markets=<csv>"
agent: "agent"
---

Create a weekly operations report for SafeTrade automated trading.

## Inputs
- Reporting week (required), e.g. `2026-W31`
- Strategies and markets in scope
- Weekly KPIs (as available):
  - gross_pnl
  - net_pnl
  - max_drawdown_pct
  - fill_rate_pct
  - reject_rate_pct
  - cancel_to_fill_ratio
  - slippage_avg_pct
  - websocket_disconnect_count
  - unreconciled_orders_count
- Incident summaries and postmortem links (optional)
- Risk profile and any temporary overrides used

If key metrics are missing, produce the report with placeholders and list required data gaps.

## Analysis Goals
1. Assess performance quality, not only raw PnL.
2. Evaluate reliability and risk-control discipline.
3. Highlight regressions versus prior week if prior values are provided.
4. Produce specific next-week actions with owners.

## Quality and Safety Rules
- Flag as high risk if `unreconciled_orders_count > 0`.
- Flag execution quality concern if `reject_rate_pct >= 5`.
- Flag transport stability concern if disconnect count is elevated relative to baseline.
- If `max_drawdown_pct` exceeds configured daily loss limits in any session, require corrective actions before risk expansion.
- Never include credentials or secrets.

## Output Format
Return sections in this exact order:
1) Executive Summary
2) KPI Scorecard
3) Strategy-Level Breakdown
4) Reliability and Risk Review
5) Incidents and Learnings
6) Top Regressions and Root Causes
7) Next-Week Action Plan
8) Data Gaps and Instrumentation TODOs

## Action Plan Format
For each action include:
- id
- priority (`P0`, `P1`, `P2`)
- owner
- due_date
- action
- expected_metric_impact
- validation_query

## Optional Add-ons
If requested, also provide:
- A stakeholder-friendly one-page summary
- A markdown table suitable for team standup
- A compact JSON summary for dashboard ingestion
