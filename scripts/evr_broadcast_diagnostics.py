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

    from_address = admin_wallet.get_address(0)
    to_address = system_wallet.get_address(0)
    admin_wif = admin_wallet.get_wif(0)

    report = {
        'from': from_address,
        'to': to_address,
        'amount_evr': '0.01',
    }

    original_get_backends = RPC._get_backends
    RPC._get_backends = lambda network_mode, rpc_endpoint_mode: [
        ('public', RPC._get_public_client(network_mode))
    ]

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('public')

    try:
        raw = create_raw_evr_transaction(
            from_address=from_address,
            to_address=to_address,
            amount_evr=Decimal('0.01'),
            change_address=from_address,
            fee_evr=Decimal('0.01'),
        )
        report['raw_outputs'] = raw.get('outputs')

        signed = sign_raw_transaction(raw['raw_tx'], wif_keys=[admin_wif])
        if isinstance(signed, dict):
            signed_hex = signed.get('hex')
            report['sign_complete'] = bool(signed.get('complete'))
            report['signed_hex_len'] = len(signed_hex or '')
        else:
            signed_hex = str(signed or '')
            report['sign_complete'] = bool(signed_hex)
            report['signed_hex_len'] = len(signed_hex)

        if signed_hex:
            try:
                decoded = RPC.decoderawtransaction(signed_hex)
                report['decoded_txid'] = decoded.get('txid')
                report['decoded_vout_count'] = len(decoded.get('vout', []))
            except Exception as exc:
                report['decode_error'] = str(exc)

            try:
                accept = RPC.testmempoolaccept([signed_hex])
                report['testmempoolaccept'] = accept
            except Exception as exc:
                report['testmempoolaccept_error'] = str(exc)

            try:
                txid = RPC.sendrawtransaction(signed_hex)
                report['sendrawtransaction_ok'] = True
                report['txid'] = txid
            except Exception as exc:
                report['sendrawtransaction_ok'] = False
                report['sendrawtransaction_error'] = str(exc)

    finally:
        RPC._get_backends = original_get_backends
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
