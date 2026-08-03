---
description: "Tune SafeTrade strategy parameters using risk and execution constraints, then output an experiment plan with expected KPI impact."
name: "SafeTrade Strategy Parameter Tuning"
argument-hint: "strategy=<market-making|momentum|mean-reversion> profile=<conservative|balanced|aggressive> markets=<csv>"
agent: "agent"
---

Design a controlled parameter tuning plan for a SafeTrade strategy.

## Inputs
- strategy type
- current parameter set
- target markets
- current KPIs:
  - net_pnl
  - drawdown_pct
  - fill_rate_pct
  - reject_rate_pct
  - slippage_avg_pct
  - cancel_to_fill_ratio
- hard risk limits that cannot be exceeded

If parameters or KPIs are missing, ask concise follow-up questions and stop.

## Tuning Goals
1. Improve risk-adjusted returns, not only PnL.
2. Reduce execution waste (rejects, excess cancels, slippage).
3. Preserve strict risk guardrails.

## Method
- Propose 3-6 parameter hypotheses.
- For each hypothesis include:
  - rationale
  - expected KPI movement
  - failure conditions
- Build a phased test sequence from safest to riskiest.
- Keep one-variable changes when possible.

## Safety Rules
- No recommendation may increase configured daily loss cap.
- If reject_rate_pct >= 5, prioritize execution-quality fixes before risk expansion.
- If drawdown near limit, require smaller size or fewer markets during tests.

## Output Format
Return sections in this exact order:
1) Current State Snapshot
2) Tuning Hypotheses
3) Experiment Plan (Phased)
4) Risk Controls During Tests
5) Success and Stop Criteria
6) Recommended Next Configuration
