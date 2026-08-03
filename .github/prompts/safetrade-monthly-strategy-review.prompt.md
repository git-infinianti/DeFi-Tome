---
description: "Review monthly SafeTrade strategy performance, compare profiles, detect execution drift, and recommend risk/parameter retuning."
name: "SafeTrade Monthly Strategy Review"
argument-hint: "month=<YYYY-MM> strategies=<csv> profiles=<csv> markets=<csv>"
agent: "agent"
---

Create a monthly strategy review for SafeTrade automated trading.

## Inputs
- month
- strategies, profiles, markets in scope
- monthly KPIs by strategy/profile:
  - gross_pnl, net_pnl
  - max_drawdown_pct
  - fill_rate_pct
  - reject_rate_pct
  - slippage_avg_pct
  - cancel_to_fill_ratio
  - disconnect_count
  - unreconciled_orders_count
- incident summaries (optional)

If key KPI groups are missing, report data gaps and continue with best effort.

## Analysis Goals
1. Compare strategy quality across profiles.
2. Detect drift in execution quality and reliability.
3. Recommend retuning and risk profile changes.

## Risk Review Rules
- Any unreconciled orders in live mode is a critical governance issue.
- Rising reject and slippage together indicates microstructure mismatch risk.
- Drawdown breaches require risk cap review before profile expansion.

## Output Format
Return sections in this exact order:
1) Executive Summary
2) Profile Comparison Table
3) Strategy-by-Strategy Findings
4) Drift and Reliability Analysis
5) Risk Governance Findings
6) Retuning Recommendations
7) Next-Month Action Plan
8) Data Gaps
