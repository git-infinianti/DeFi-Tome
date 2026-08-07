import json
import os
import sys

REPO_TOME = '/Users/chiefton/Documents/GitHub/DeFiTome/Tome'
if REPO_TOME not in sys.path:
    sys.path.insert(0, REPO_TOME)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tome.settings')

import django

django.setup()

from Tome.rpc_client import (
    RPC,
    clear_active_network_mode,
    clear_active_rpc_endpoint_mode,
    set_active_network_mode,
    set_active_rpc_endpoint_mode,
)


def safe_call(name, fn):
    try:
        result = fn()
        return {
            'call': name,
            'ok': True,
            'result': result,
        }
    except Exception as exc:
        return {
            'call': name,
            'ok': False,
            'error': str(exc),
        }


def run_mode(endpoint_mode):
    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode(endpoint_mode)

    return {
        'endpoint_mode': endpoint_mode,
        'calls': [
            safe_call('getblockchaininfo', lambda: RPC.getblockchaininfo()),
            safe_call('getbestblockhash', lambda: RPC.getbestblockhash()),
            safe_call('getmempoolinfo', lambda: RPC.getmempoolinfo()),
        ],
    }


def main():
    report = {
        'environment': {
            'RPC_TESTNET_HOST': os.getenv('RPC_TESTNET_HOST'),
            'RPC_TESTNET_PORT': os.getenv('RPC_TESTNET_PORT'),
            'RPC_TESTNET_URL': os.getenv('RPC_TESTNET_URL'),
            'RPC_TESTNET_SCHEME': os.getenv('RPC_TESTNET_SCHEME'),
            'RPC_TESTNET_PATH': os.getenv('RPC_TESTNET_PATH'),
            'DEFAULT_EVRMORE_RPC_ENDPOINT_MODE': os.getenv('DEFAULT_EVRMORE_RPC_ENDPOINT_MODE'),
        },
        'modes': [],
    }

    try:
        report['modes'].append(run_mode('public'))
        report['modes'].append(run_mode('local'))
    finally:
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
