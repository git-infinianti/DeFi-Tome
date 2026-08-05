# EVRMore RPC Method Pack

Use these methods as a practical baseline for market-research and DEX architecture workflows.

## Health And Chain Liveness
- getblockchaininfo
- getbestblockhash
- getblockcount
- getmempoolinfo
- uptime

## Asset Discovery And Validation
- listassets
- getassetdata
- listmyassets
- listassetbalancesbyaddress
- listaddressesbyasset

## Address And UTXO Introspection
- getaddressbalance
- getaddressutxos
- getaddresstxids
- getaddressdeltas
- getaddressmempool

## Transaction And Settlement Support
- createrawtransaction
- fundrawtransaction
- signrawtransaction
- sendrawtransaction
- decoderawtransaction
- getrawtransaction

## Reliability Notes
- Public endpoints are JSON-RPC over HTTPS at /rpc.
- Root path / may reject POST with Cannot POST /.
- Always verify chain field in getblockchaininfo:
  - mainnet endpoint should return chain=main
  - testnet endpoint should return chain=test
