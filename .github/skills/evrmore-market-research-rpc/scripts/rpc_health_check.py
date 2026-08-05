#!/usr/bin/env python3
"""Check EVRMore public RPC health and emit a compact JSON report.

Usage:
  python .github/skills/evrmore-market-research-rpc/scripts/rpc_health_check.py
  python .github/skills/evrmore-market-research-rpc/scripts/rpc_health_check.py --network mainnet
  python .github/skills/evrmore-market-research-rpc/scripts/rpc_health_check.py --network both --timeout 8
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
from datetime import datetime, timezone
from typing import Any, Dict, List

ENDPOINTS = {
    "mainnet": "https://evr-rpc-mainnet.evrmorecoin.org/rpc",
    "testnet": "https://evr-rpc-testnet.evrmorecoin.org/rpc",
}

METHODS = [
    "help",
    "getblockchaininfo",
    "getbestblockhash",
    "getmempoolinfo",
]


def rpc_call(url: str, method: str, timeout: int, verify_tls: bool) -> Dict[str, Any]:
    payload = json.dumps(
        {
            "jsonrpc": "1.0",
            "id": f"health-{method}",
            "method": method,
            "params": [],
        }
    )

    command = [
        "curl",
        "-sS",
        "-X",
        "POST",
        url,
        "-H",
        "content-type: text/plain",
        "--data",
        payload,
        "--max-time",
        str(timeout),
    ]
    if not verify_tls:
        command.insert(1, "-k")

    start = time.perf_counter()
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    if completed.returncode != 0:
        raise ValueError(completed.stderr.strip() or f"curl failed with code {completed.returncode}")

    body = completed.stdout

    parsed = json.loads(body)
    return {
        "ok": parsed.get("error") is None,
        "latency_ms": elapsed_ms,
        "result": parsed.get("result"),
        "error": parsed.get("error"),
    }


def run_network_check(network: str, timeout: int, verify_tls: bool) -> Dict[str, Any]:
    url = ENDPOINTS[network]
    checks: Dict[str, Any] = {}

    for method in METHODS:
        try:
            checks[method] = rpc_call(url, method, timeout=timeout, verify_tls=verify_tls)
        except (TimeoutError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
            checks[method] = {
                "ok": False,
                "latency_ms": None,
                "result": None,
                "error": str(exc),
            }

    def is_whitelist_error(item: Dict[str, Any]) -> bool:
        error_value = item.get("error")
        if not error_value:
            return False
        return "whitelist" in str(error_value).lower()

    all_ok = all(item.get("ok") for item in checks.values())
    any_whitelist = any(is_whitelist_error(item) for item in checks.values())
    any_reachable = any(item.get("ok") or is_whitelist_error(item) for item in checks.values())

    chain = None
    blocks = None
    mempool_size = None
    mempool_bytes = None

    blockchain = checks.get("getblockchaininfo", {}).get("result")
    mempool = checks.get("getmempoolinfo", {}).get("result")

    if isinstance(blockchain, dict):
        chain = blockchain.get("chain")
        blocks = blockchain.get("blocks")

    if isinstance(mempool, dict):
        mempool_size = mempool.get("size")
        mempool_bytes = mempool.get("bytes")

    access_mode = "full"
    if any_whitelist and not all_ok:
        access_mode = "restricted"
    elif not any_reachable:
        access_mode = "unreachable"

    return {
        "network": network,
        "url": url,
        "ok": all_ok or any_reachable,
        "summary": {
            "access_mode": access_mode,
            "chain": chain,
            "blocks": blocks,
            "mempool_size": mempool_size,
            "mempool_bytes": mempool_bytes,
        },
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EVRMore RPC health checker")
    parser.add_argument(
        "--network",
        choices=["mainnet", "testnet", "both"],
        default="both",
        help="Which network endpoint(s) to check.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification. Use only when local CA trust is unavailable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    networks: List[str]
    if args.network == "both":
        networks = ["mainnet", "testnet"]
    else:
        networks = [args.network]

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_network": args.network,
        "timeout_seconds": args.timeout,
        "verify_tls": not args.insecure,
        "results": [
            run_network_check(network, timeout=args.timeout, verify_tls=not args.insecure)
            for network in networks
        ],
    }

    print(json.dumps(report, indent=2))

    return 0 if all(item.get("ok") for item in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
