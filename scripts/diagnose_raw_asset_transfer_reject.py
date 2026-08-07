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
from Wallet.rpc import (
    create_raw_asset_transfer_transaction,
    sign_raw_transaction,
)
from Tome.rpc_client import (
    RPC,
    clear_active_network_mode,
    clear_active_rpc_endpoint_mode,
    set_active_network_mode,
    set_active_rpc_endpoint_mode,
)


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: diagnose_raw_asset_transfer_reject.py <ASSET_NAME> [FEE_EVR]')

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
        'fee_evr': str(fee_evr) if fee_evr is not None else None,
    }

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('local')

    try:
        raw = create_raw_asset_transfer_transaction(
            from_address=from_address,
            to_address=to_address,
            asset_name=asset_name,
            asset_quantity=Decimal('1'),
            change_address=coin_change_address,
            fee_evr=fee_evr,
            asset_change_address=from_address,
        )
        report['raw_outputs'] = raw.get('outputs')

        signed = sign_raw_transaction(raw['raw_tx'], wif_keys=[admin_wif])
        signed_hex = signed.get('hex') if isinstance(signed, dict) else str(signed)
        report['signed_hex_len'] = len(signed_hex or '')

        if signed_hex:
            try:
                report['testmempoolaccept'] = RPC.testmempoolaccept([signed_hex])
            except Exception as exc:
                report['testmempoolaccept_error'] = str(exc)

            try:
                report['decode'] = RPC.decoderawtransaction(signed_hex)
            except Exception as exc:
                report['decode_error'] = str(exc)

            try:
                report['sendrawtransaction'] = RPC.sendrawtransaction(signed_hex)
            except Exception as exc:
                report['sendrawtransaction_error'] = str(exc)

    except Exception as exc:
        report['error'] = str(exc)
    finally:
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
