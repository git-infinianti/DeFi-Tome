#!/usr/bin/env python3
"""Validate local Evrmore RPC compatibility for this project's implementation.

This script is intended as a backup readiness check for local-node RPC usage.
It reads evrmore.conf, performs core health checks, and verifies command
availability through help lookups.
"""

from __future__ import annotations

import argparse
import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
import urllib.error
import urllib.request

DEFAULT_CONF = Path.home() / "Library/Application Support/Evrmore/evrmore.conf"

REQUIRED_COMMANDS = [
    "getblockchaininfo",
    "getblockcount",
    "getmininginfo",
    "getblockhash",
    "getblock",
    "getrawtransaction",
    "getaddressbalance",
    "listassetbalancesbyaddress",
    "getaddressutxos",
    "createrawtransaction",
    "estimatesmartfee",
    "sendrawtransaction",
]

BASELINE_METHODS = [
    "getblockchaininfo",
    "getblockcount",
    "getrpcinfo",
    "uptime",
]


@dataclass
class RpcConfig:
    rpcuser: str
    rpcpassword: str
    rpcport: str
    rpchost: str


def load_conf(conf_path: Path) -> RpcConfig:
    if not conf_path.exists():
        raise FileNotFoundError(f"RPC config not found: {conf_path}")

    parsed: Dict[str, str] = {}
    for raw_line in conf_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()

    rpcuser = parsed.get("rpcuser", "")
    rpcpassword = parsed.get("rpcpassword", "")
    rpcport = parsed.get("rpcport", "8819")
    rpchost = parsed.get("rpcconnect", "127.0.0.1")

    if not rpcuser or not rpcpassword:
        raise ValueError("Missing rpcuser/rpcpassword in evrmore.conf")

    return RpcConfig(
        rpcuser=rpcuser,
        rpcpassword=rpcpassword,
        rpcport=rpcport,
        rpchost=rpchost,
    )


def rpc_call(config: RpcConfig, method: str, params: List[object] | None = None, timeout: int = 12):
    payload = json.dumps(
        {
            "jsonrpc": "1.0",
            "id": "backup-probe",
            "method": method,
            "params": params or [],
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"http://{config.rpchost}:{config.rpcport}/",
        data=payload,
        headers={"Content-Type": "text/plain"},
    )

    token = base64.b64encode(f"{config.rpcuser}:{config.rpcpassword}".encode("utf-8")).decode("ascii")
    request.add_header("Authorization", f"Basic {token}")

    with urllib.request.urlopen(request, timeout=timeout) as response:
        response_body = response.read().decode("utf-8")

    parsed = json.loads(response_body)
    return parsed.get("result"), parsed.get("error")


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Evrmore RPC backup probe")
    parser.add_argument("--conf", type=Path, default=DEFAULT_CONF, help="Path to evrmore.conf")
    parser.add_argument("--timeout", type=int, default=12, help="Timeout in seconds")
    args = parser.parse_args()

    report = {
        "config": {
            "conf_path": str(args.conf),
        },
        "baseline": {},
        "command_coverage": {
            "required_commands": REQUIRED_COMMANDS,
            "available": [],
            "missing": [],
            "errors": {},
        },
        "ok": False,
    }

    try:
        config = load_conf(args.conf)
        report["config"].update(
            {
                "rpc_host": config.rpchost,
                "rpc_port": config.rpcport,
            }
        )
    except Exception as exc:
        report["setup_error"] = str(exc)
        print(json.dumps(report, indent=2))
        return 1

    baseline_ok = True
    for method in BASELINE_METHODS:
        try:
            result, error = rpc_call(config, method, timeout=args.timeout)
            report["baseline"][method] = {
                "ok": error is None,
                "error": error,
                "has_result": result is not None,
            }
            if error is not None:
                baseline_ok = False
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            report["baseline"][method] = {
                "ok": False,
                "error": str(exc),
                "has_result": False,
            }
            baseline_ok = False

    available = []
    missing = []
    command_errors: Dict[str, str] = {}

    for command in REQUIRED_COMMANDS:
        try:
            result, error = rpc_call(config, "help", [command], timeout=args.timeout)
            if error is not None:
                missing.append(command)
                command_errors[command] = str(error)
                continue

            help_text = str(result or "")
            if "unknown command" in help_text.lower():
                missing.append(command)
                command_errors[command] = "unknown command"
            else:
                available.append(command)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            missing.append(command)
            command_errors[command] = str(exc)

    report["command_coverage"]["available"] = available
    report["command_coverage"]["missing"] = missing
    report["command_coverage"]["errors"] = command_errors

    coverage_ok = len(missing) == 0
    report["ok"] = baseline_ok and coverage_ok

    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
