#!/usr/bin/env python3
"""Validate .github/docs/commands-cheatsheet.md against live Evrmore RPC help output.

Usage:
  python3 scripts/verify_rpc_cheatsheet.py
    python3 scripts/verify_rpc_cheatsheet.py --markdown .github/docs/commands-cheatsheet.md
  python3 scripts/verify_rpc_cheatsheet.py --strict

Exit codes:
  0 = all listed commands recognized
  1 = unknown commands or runtime validation errors
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_CONF = Path.home() / "Library/Application Support/Evrmore/evrmore.conf"
DEFAULT_MD = Path(".github/docs/commands-cheatsheet.md")
COMMAND_LINE_PATTERN = re.compile(r'^\s*-\s+`([^`]+)`\s*$')


@dataclass
class RpcConfig:
    rpcuser: str
    rpcpassword: str
    rpcport: str


def load_evrmore_conf(conf_path: Path) -> RpcConfig:
    if not conf_path.exists():
        raise FileNotFoundError(f"RPC config not found: {conf_path}")

    conf: Dict[str, str] = {}
    for line in conf_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        conf[key.strip()] = value.strip()

    rpcuser = conf.get("rpcuser", "")
    rpcpassword = conf.get("rpcpassword", "")
    rpcport = conf.get("rpcport", "8819")

    if not rpcuser or not rpcpassword:
        raise ValueError(
            f"Missing rpcuser/rpcpassword in {conf_path}."
        )

    return RpcConfig(rpcuser=rpcuser, rpcpassword=rpcpassword, rpcport=rpcport)


def extract_commands(markdown_path: Path) -> List[str]:
    if not markdown_path.exists():
        raise FileNotFoundError(f"Cheatsheet not found: {markdown_path}")

    commands: List[str] = []
    for line in markdown_path.read_text().splitlines():
        match = COMMAND_LINE_PATTERN.match(line)
        if not match:
            continue
        body = match.group(1).strip()
        if not body:
            continue
        name = body.split()[0]
        if name and name not in commands:
            commands.append(name)
    return commands


def rpc_help(config: RpcConfig, command: str, host: str) -> str:
    payload = json.dumps(
        {
            "jsonrpc": "1.0",
            "id": "cheatsheet-verify",
            "method": "help",
            "params": [command],
        }
    ).encode("utf-8")

    url = f"http://{host}:{config.rpcport}/"
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "text/plain"},
    )

    token = base64.b64encode(
        f"{config.rpcuser}:{config.rpcpassword}".encode("utf-8")
    ).decode("ascii")
    request.add_header("Authorization", f"Basic {token}")

    with urllib.request.urlopen(request, timeout=15) as response:
        body = response.read().decode("utf-8")

    parsed = json.loads(body)
    result = parsed.get("result")
    if not isinstance(result, str):
        raise ValueError(f"Unexpected RPC result type for {command}: {type(result).__name__}")
    return result


def validate_commands(commands: List[str], config: RpcConfig, host: str) -> Tuple[List[str], List[Tuple[str, str]]]:
    unknown: List[str] = []
    errors: List[Tuple[str, str]] = []

    for command in commands:
        try:
            help_text = rpc_help(config, command, host=host)
            if "unknown command" in help_text.lower():
                unknown.append(command)
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            errors.append((command, str(exc)))

    return unknown, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify RPC command cheatsheet against live node help output.")
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MD, help="Path to the cheatsheet markdown file.")
    parser.add_argument("--conf", type=Path, default=DEFAULT_CONF, help="Path to evrmore.conf.")
    parser.add_argument("--host", default="127.0.0.1", help="RPC host (default: 127.0.0.1).")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors (non-zero exit when unknown commands exist).",
    )
    args = parser.parse_args()

    try:
        config = load_evrmore_conf(args.conf)
        commands = extract_commands(args.markdown)
    except Exception as exc:
        print(f"setup_error: {exc}")
        return 1

    unknown, errors = validate_commands(commands, config=config, host=args.host)

    print(f"commands_total={len(commands)}")
    print(f"commands_unknown={len(unknown)}")
    print(f"commands_errors={len(errors)}")

    if unknown:
        print("unknown_commands:")
        for command in unknown:
            print(f"- {command}")

    if errors:
        print("validation_errors:")
        for command, error in errors:
            print(f"- {command}: {error}")

    if errors:
        return 1

    if unknown and args.strict:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
