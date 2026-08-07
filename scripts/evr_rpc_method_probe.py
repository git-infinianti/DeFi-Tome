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


def main():
    methods = [
        'getblockchaininfo',
        'getbestblockhash',
        'getmempoolinfo',
        'validateaddress',
        'getaddressbalance',
        'getaddressutxos',
        'createrawtransaction',
        'signrawtransaction',
        'sendrawtransaction',
        'issue',
        'transferfromaddress',
        'listassets',
    ]

    result = {}

    original_get_backends = RPC._get_backends
    RPC._get_backends = lambda network_mode, rpc_endpoint_mode: [
        ('public', RPC._get_public_client(network_mode))
    ]

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('public')

    try:
        for method_name in methods:
            try:
                method_help = RPC.help(method_name)
                result[method_name] = {
                    'available': True,
                    'help_len': len(str(method_help)),
                }
            except Exception as exc:
                result[method_name] = {
                    'available': False,
                    'error': str(exc),
                }
    finally:
        RPC._get_backends = original_get_backends
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
