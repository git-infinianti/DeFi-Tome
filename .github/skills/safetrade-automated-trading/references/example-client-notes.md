# SafeTrade Example Client Notes

Repository reference: `https://github.com/safetrade-exchange/example-client`

## Structure
- `api.py`: signed request client and order/account REST helpers
- `ws.py`: websocket connection + subscribe/unsubscribe + receive loop
- `wsstore.py`: public/private websocket manager
- `manager.py`: orchestration wrapper and callback handling
- `ticker.py`: ticker model object
- `main.py`: basic end-to-end usage example

## Reusable Patterns
- Lazily initialize websocket manager only when needed.
- Keep one callback path that handles all stream payloads.
- Maintain in-memory ticker/order state updated by stream messages.
- Wrap GET/POST in helper methods and centralize auth header generation.

## Auth Implementation Pattern
- Nonce generated from current time in milliseconds.
- Signature generated via HMAC-SHA256 and hex encoded.
- Attach signed headers to private requests.

## Trading Flow Demonstrated
1. Create client with base URL + key + secret.
2. Call account endpoint (`members/me`) to verify auth.
3. Query orders.
4. Create order with market, side, amount, optional price.
5. Subscribe to public and private streams.

## Improvements Recommended For Production Bots
- Add retries with bounded exponential backoff.
- Use strict request/response schemas and runtime validation.
- Add idempotency protection for create/cancel requests.
- Add websocket reconnect with replay/reconciliation logic.
- Separate strategy logic from transport and execution layers.
- Add persistent event/audit logging and metrics.
- Add kill switch and hard drawdown guardrails.
