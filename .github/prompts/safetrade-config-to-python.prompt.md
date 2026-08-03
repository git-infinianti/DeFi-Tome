---
description: "Convert SafeTrade bot risk config JSON into a ready-to-use Python settings module with dataclasses, validation checks, and optional env overrides."
name: "SafeTrade Config To Python"
argument-hint: "module=<bot_config.py> env_prefix=<BOT_>"
agent: "agent"
---

Convert a SafeTrade bot configuration JSON payload into a Python settings module suitable for runtime loading.

## Input Contract
Expect the user to provide JSON matching this shape (or equivalent keys):
- profile
- mode
- equity
- currency
- markets
- limits
- go_live_gates

If JSON is missing or malformed, ask for corrected JSON only and stop.

## What To Produce
Generate a single Python module that includes:
1. Typed dataclasses:
- `Limits`
- `GoLiveGates`
- `BotConfig`

2. Validation helpers:
- Ensure percentages are positive and reasonable.
- Ensure markets list is non-empty.
- Ensure daily loss percent is less than 100.
- Ensure open orders and throttles are positive integers.

3. Config loader:
- `load_config()` that builds `BotConfig` from embedded JSON values.
- Optional environment override support using `env_prefix`.
- Parse numeric env vars safely with explicit errors.

4. Export constants:
- `CONFIG` initialized from `load_config()`.

## Behavioral Rules
- Default to Python 3.11+ style typing.
- Use only standard library unless user asks otherwise.
- Keep the module deterministic and side-effect free except reading environment variables.
- Do not include API keys or secrets.
- If mode is `live`, add one short warning comment near `CONFIG`.

## Output Format
Return sections in this order:
1) `Assumptions`
2) `Python Module` (single fenced code block)
3) `How To Use` (3-6 bullet points)

## Optional Enhancements
If the user asks, also include:
- A second function `as_dict(config: BotConfig) -> dict`
- A function to compute per-market budget summaries
- A minimal pytest snippet for validation checks
