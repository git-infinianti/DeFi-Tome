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
from Wallet.rpc import create_and_send_evr_transaction
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

    report = {
        'from': from_address,
        'to': to_address,
        'amount_evr': '0.005',
        'fee_evr': '0.003',
    }

    original_get_backends = RPC._get_backends
    RPC._get_backends = lambda network_mode, rpc_endpoint_mode: [
        ('public', RPC._get_public_client(network_mode))
    ]

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('public')

    try:
        tx = create_and_send_evr_transaction(
            from_address=from_address,
            to_address=to_address,
            amount_evr=Decimal('0.005'),
            change_address=from_address,
            fee_evr=Decimal('0.003'),
            wif_keys=[system_wif],
        )
        txid = tx.get('txid')
        report['txid'] = txid

        try:
            raw = RPC.getrawtransaction(txid, True)
            report['verified_by_getrawtransaction'] = True
            report['vout_count'] = len(raw.get('vout', [])) if isinstance(raw, dict) else None
        except Exception as exc:
            report['verified_by_getrawtransaction'] = False
            report['verify_error'] = str(exc)

    except Exception as exc:
        report['error'] = str(exc)

    finally:
        RPC._get_backends = original_get_backends
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
