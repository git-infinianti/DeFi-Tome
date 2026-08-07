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

from django.contrib.auth.models import User
from Wallet.wallet import Wallet
from Wallet.rpc import create_raw_evr_transaction, sign_raw_transaction
from Tome.rpc_client import (
    RPC,
    clear_active_network_mode,
    clear_active_rpc_endpoint_mode,
    set_active_network_mode,
    set_active_rpc_endpoint_mode,
)


def main():
    admin = User.objects.get(username='admin')
    system = User.objects.get(username='system')

    admin_wallet = Wallet(admin.user_wallet.entropy, admin.user_wallet.passphrase, network_mode='testnet')
    system_wallet = Wallet(system.user_wallet.entropy, system.user_wallet.passphrase, network_mode='testnet')

    to_address = admin_wallet.get_address(0)
    from_address = system_wallet.get_address(0)
    system_wif = system_wallet.get_wif(0)

    fees = [Decimal('0.0001'), Decimal('0.0005'), Decimal('0.001'), Decimal('0.002'), Decimal('0.003'), Decimal('0.005')]

    report = {
        'from': from_address,
        'to': to_address,
        'amount_evr': '0.005',
        'results': [],
    }

    original_get_backends = RPC._get_backends
    RPC._get_backends = lambda network_mode, rpc_endpoint_mode: [
        ('public', RPC._get_public_client(network_mode))
    ]

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('public')

    try:
        for fee in fees:
            row = {'fee_evr': str(fee)}
            try:
                raw = create_raw_evr_transaction(
                    from_address=from_address,
                    to_address=to_address,
                    amount_evr=Decimal('0.005'),
                    change_address=from_address,
                    fee_evr=fee,
                )
                signed = sign_raw_transaction(raw['raw_tx'], wif_keys=[system_wif])
                signed_hex = signed.get('hex') if isinstance(signed, dict) else str(signed)
                if not signed_hex:
                    row['ok'] = False
                    row['error'] = 'empty signed hex'
                else:
                    try:
                        accept = RPC.testmempoolaccept([signed_hex])
                        row['testmempoolaccept'] = accept
                        row['ok'] = True
                    except Exception as exc:
                        row['ok'] = False
                        row['error'] = str(exc)
            except Exception as exc:
                row['ok'] = False
                row['error'] = str(exc)

            report['results'].append(row)

    finally:
        RPC._get_backends = original_get_backends
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
