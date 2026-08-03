---
description: "Generate a minimal pytest suite for a SafeTrade Python bot config module, focused on validation, env overrides, and safety checks."
name: "SafeTrade Config Pytest Generator"
argument-hint: "module=<bot_config.py> test_file=<tests/test_bot_config.py>"
agent: "agent"
---

Generate a concise pytest file for a SafeTrade bot config module.

## Inputs
- Target module path (required), e.g. `bot_config.py`
- Optional target test file path, e.g. `tests/test_bot_config.py`
- Optional assumptions about public API names (defaults below)

Default expected API in module:
- dataclasses: `Limits`, `GoLiveGates`, `BotConfig`
- loader: `load_config()`
- constant: `CONFIG`

If the module API differs, infer names from user-provided code and adapt tests.

## Test Goals
Cover only high-value checks:
1. `load_config()` returns a valid `BotConfig` object.
2. Markets list is non-empty.
3. Percentage limits are positive and daily loss is `< 100`.
4. Integer limits (`max_open_orders_per_market`, throttles, breaker counts) are positive.
5. Environment overrides are applied correctly.
6. Invalid environment values raise clear errors.
7. Live mode config still enforces safety limits.

## Constraints
- Use `pytest` and stdlib only.
- Keep test file small and readable.
- Avoid brittle tests tied to exact wording of error messages.
- Use monkeypatch for env vars.
- If the module has helper validators, test through public APIs first.

## Output Format
Return sections in this order:
1) `Assumptions`
2) `Pytest File` (single fenced code block)
3) `How To Run` (commands)

## Optional Add-on
If requested, also return a tiny `conftest.py` with shared fixtures for sample JSON payloads.
