import json
import os
import sys
from decimal import Decimal

REPO_TOME = '/Users/chiefton/Documents/GitHub/DeFiTome/Tome'
if REPO_TOME not in sys.path:
    sys.path.insert(0, REPO_TOME)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tome.settings')

import django

django.setup()

from Wallet.rpc import create_raw_evr_transaction
from Tome.rpc_client import (
    RPC,
    clear_active_network_mode,
    clear_active_rpc_endpoint_mode,
    set_active_network_mode,
    set_active_rpc_endpoint_mode,
)


def main():
    from_address = 'msmLKdT7nnGGZocTVajs2W6ohjy13gxDyz'
    to_address = 'mnnU7V6W4Kk2XQsSTSWQyyyZpwShuyNNcU'

    original_get_backends = RPC._get_backends
    RPC._get_backends = lambda network_mode, rpc_endpoint_mode: [
        ('public', RPC._get_public_client(network_mode))
    ]

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('public')

    try:
        tx_default = create_raw_evr_transaction(
            from_address=from_address,
            to_address=to_address,
            amount_evr=Decimal('0.01'),
            change_address=from_address,
        )
        tx_high = create_raw_evr_transaction(
            from_address=from_address,
            to_address=to_address,
            amount_evr=Decimal('0.01'),
            change_address=from_address,
            fee_evr=Decimal('0.01'),
        )

        print(json.dumps({'default': tx_default['outputs'], 'high_fee': tx_high['outputs']}, indent=2, sort_keys=True))
    finally:
        RPC._get_backends = original_get_backends
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()


if __name__ == '__main__':
    main()
