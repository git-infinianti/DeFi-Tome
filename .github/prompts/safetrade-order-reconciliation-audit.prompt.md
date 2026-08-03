---
description: "Audit SafeTrade local order state versus exchange state and produce reconciliation fixes with confidence levels."
name: "SafeTrade Order Reconciliation Audit"
argument-hint: "window=<last_1h|last_24h|custom> mode=<paper|live> markets=<csv>"
agent: "agent"
---

Perform a reconciliation audit between local bot state and exchange truth.

## Inputs
- time window
- markets
- local order state snapshot
- exchange order/trade snapshots
- optional private websocket event excerpts

If key state snapshots are missing, ask concise follow-up questions and stop.

## Audit Tasks
1. Match local and exchange orders by id.
2. Identify mismatches:
- missing local orders
- stale local status
- fill quantity mismatch
- canceled/filled divergence
- orphaned local orders without exchange record

3. Estimate operational risk for each mismatch.
4. Recommend deterministic repair steps.

## Classification
Use one of:
- INFO
- WARNING
- CRITICAL

Mark as CRITICAL when:
- unreconciled open orders exist
- executed quantity mismatch can impact risk limits
- cancel status uncertain in live mode

## Output Format
Return sections in this exact order:
1) Audit Summary
2) Mismatch Table
3) Risk Classification
4) Repair Plan (Ordered)
5) Verification Queries
6) Prevention Improvements

## Repair Plan Rules
- Prefer idempotent, replay-safe actions.
- Recommend write-ahead audit logging for every repair.
- Include a rollback note if a repair can affect exposure.
