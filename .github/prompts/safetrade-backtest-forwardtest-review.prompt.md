---
description: "Evaluate backtest and forward-test quality for SafeTrade strategies and produce go/no-go recommendations for paper or live progression."
name: "SafeTrade Backtest Forward-Test Review"
argument-hint: "strategy=<market-making|momentum|mean-reversion> next_mode=<paper|live> markets=<csv>"
agent: "agent"
---

Assess whether test evidence is strong enough to progress strategy deployment.

## Inputs
- strategy and markets
- backtest summary:
  - period, sample size, assumptions
  - net_pnl, drawdown, win_rate, sharpe_like_metric
- forward-test or paper-test summary:
  - runtime_hours, intents_count, fill_rate_pct, reject_rate_pct, slippage_avg_pct
- known caveats and model limitations

If required evidence is missing, ask concise follow-up questions and stop.

## Review Goals
1. Detect overfitting risk.
2. Check assumption realism versus observed execution.
3. Assess robustness under varying conditions.
4. Decide progression readiness.

## Heuristics
- Penalize unstable performance across subperiods.
- Penalize heavy dependence on unrealistic slippage or fill assumptions.
- Require alignment between backtest expectations and forward-test evidence.

## Decision Output
Use one:
- PROGRESS
- PROGRESS-WITH-GUARDS
- HOLD

## Output Format
Return sections in this exact order:
1) Evidence Summary
2) Backtest Quality Assessment
3) Forward-Test Quality Assessment
4) Assumption Gap Analysis
5) Decision (PROGRESS | PROGRESS-WITH-GUARDS | HOLD)
6) Required Improvements Before Next Stage
