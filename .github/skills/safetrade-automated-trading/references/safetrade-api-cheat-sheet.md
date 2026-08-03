# SafeTrade API Cheat Sheet

## Base
- REST base URL: `https://safe.trade/api/v2`
- Public swagger: `https://safetrade.com/api/v2/trade/public/swagger.json`

## Authentication
- Auth methods described by docs: Basic Auth and HMAC-SHA256 signed requests.
- Signed private request headers used by reference client:
  - `X-Auth-Apikey`
  - `X-Auth-Nonce`
  - `X-Auth-Signature`
  - `Content-Type: application/json;charset=utf-8`
- Signature pattern in reference client: `hmac_sha256(secret, nonce + api_key)` hex digest.

## Public Endpoints (strategy/data)
- `GET /trade/public/markets`
- `GET /trade/public/markets/{id}`
- `GET /trade/public/markets/{id}/depth`
- `GET /trade/public/markets/{id}/k-line`
- `GET /trade/public/markets/{id}/trades`
- `GET /trade/public/tickers`
- `GET /trade/public/tickers/{market}`
- `GET /trade/public/trading_fees`

## Private Endpoints (execution/account)
- `GET /trade/account/members/me`
- `GET /trade/account/balances/spot`
- `GET /trade/market/orders`
- `POST /trade/market/orders`
- `GET /trade/market/orders/{id}`
- `POST /trade/market/orders/{id}/cancel`
- `GET /trade/market/trades`

## Order Schema Highlights
- Create order fields include `market`, `side`, `amount`, optional `price`, `stop_price`, `total`.
- `side` values: `buy`, `sell`.
- Market states and precision fields are available via market metadata.

## WebSocket
- Endpoints:
  - `GET /websocket/public`
  - `GET /websocket/private`
- Subscription message shape:
  - `{"event":"subscribe","streams":[...]} `
- Channels:
  - Public: `global.tickers`, `<market>.trades`, `<market>.depth`
  - Private: `order`, `trade`, `balance`

## Common HTTP Errors
- `400` bad request
- `401` unauthorized
- `403` forbidden
- `404` not found
- `422` invalid input
- `500` internal server error

## Bot Engineering Notes
- Build precision-safe formatting from `amount_precision` and `price_precision`.
- Validate against `min_amount` and `min_price` before create-order calls.
- Use websocket events for low-latency state updates and periodic REST reconciliation.
