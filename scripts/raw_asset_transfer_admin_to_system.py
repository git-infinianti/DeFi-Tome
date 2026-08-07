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
from Wallet.rpc import create_and_send_asset_transfer_transaction
from Tome.rpc_client import (
    clear_active_network_mode,
    clear_active_rpc_endpoint_mode,
    set_active_network_mode,
    set_active_rpc_endpoint_mode,
)


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: raw_asset_transfer_admin_to_system.py <ASSET_NAME> [FEE_EVR]')

    asset_name = sys.argv[1]
    fee_evr = Decimal(sys.argv[2]) if len(sys.argv) > 2 else None

    admin = User.objects.get(username='admin')
    system = User.objects.get(username='system')

    admin_wallet = Wallet(admin.user_wallet.entropy, admin.user_wallet.passphrase, network_mode='testnet')
    system_wallet = Wallet(system.user_wallet.entropy, system.user_wallet.passphrase, network_mode='testnet')

    from_address = admin_wallet.get_address(0)
    to_address = system_wallet.get_address(0)
    coin_change_address = admin_wallet.get_address(1)
    admin_wif = admin_wallet.get_wif(0)

    report = {
        'asset_name': asset_name,
        'from': from_address,
        'to': to_address,
        'endpoint_mode': 'local',
        'fee_evr': str(fee_evr) if fee_evr is not None else None,
    }

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('local')

    try:
        tx = create_and_send_asset_transfer_transaction(
            from_address=from_address,
            to_address=to_address,
            asset_name=asset_name,
            asset_quantity=Decimal('1'),
            change_address=coin_change_address,
            fee_evr=fee_evr,
            wif_keys=[admin_wif],
            asset_change_address=from_address,
        )
        report['ok'] = True
        report['txid'] = tx.get('txid')
        report['outputs'] = tx.get('outputs')
    except Exception as exc:
        report['ok'] = False
        report['error'] = str(exc)

    finally:
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
