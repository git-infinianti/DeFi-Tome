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
        value = fn()
        payload = {'ok': True, 'type': type(value).__name__}
        if isinstance(value, list):
            payload['count'] = len(value)
            payload['sample'] = value[:5]
        else:
            payload['value'] = value
        return name, payload
    except Exception as exc:
        return name, {'ok': False, 'error': str(exc)}


def main():
    address = 'msmLKdT7nnGGZocTVajs2W6ohjy13gxDyz'
    result = {'address': address}

    original_get_backends = RPC._get_backends
    RPC._get_backends = lambda network_mode, rpc_endpoint_mode: [
        ('public', RPC._get_public_client(network_mode))
    ]

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('public')

    try:
        calls = [
            ('getaddressbalance_obj', lambda: RPC.getaddressbalance({'addresses': [address]})),
            ('getaddressbalance_str', lambda: RPC.getaddressbalance(address)),
            ('getaddressutxos_obj', lambda: RPC.getaddressutxos({'addresses': [address]})),
            ('getaddressutxos_obj_chainInfo', lambda: RPC.getaddressutxos({'addresses': [address], 'chainInfo': True})),
            ('getaddressutxos_kwargs_list', lambda: RPC.getaddressutxos(addresses=[address])),
            ('getaddressutxos_kwargs_str', lambda: RPC.getaddressutxos(addresses=address)),
            ('listassetbalancesbyaddress', lambda: RPC.listassetbalancesbyaddress(address)),
        ]

        for name, fn in calls:
            key, payload = safe_call(name, fn)
            result[key] = payload

    finally:
        RPC._get_backends = original_get_backends
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
