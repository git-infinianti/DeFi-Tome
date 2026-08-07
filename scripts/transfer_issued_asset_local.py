import json
import os
import sys

REPO_TOME = '/Users/chiefton/Documents/GitHub/DeFiTome/Tome'
if REPO_TOME not in sys.path:
    sys.path.insert(0, REPO_TOME)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tome.settings')

import django

django.setup()

from django.contrib.auth.models import User
from Wallet.wallet import Wallet
from Tome.rpc_client import (
    RPC,
    clear_active_network_mode,
    clear_active_rpc_endpoint_mode,
    set_active_network_mode,
    set_active_rpc_endpoint_mode,
)


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: transfer_issued_asset_local.py <ASSET_NAME>')

    asset_name = sys.argv[1]

    admin = User.objects.get(username='admin')
    system = User.objects.get(username='system')

    admin_wallet = Wallet(admin.user_wallet.entropy, admin.user_wallet.passphrase, network_mode='testnet')
    system_wallet = Wallet(system.user_wallet.entropy, system.user_wallet.passphrase, network_mode='testnet')

    admin_addr = admin_wallet.get_address(0)
    system_addr = system_wallet.get_address(0)

    report = {
        'asset_name': asset_name,
        'from': admin_addr,
        'to': system_addr,
        'endpoint_mode': 'local',
    }

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('local')

    try:
        txid = RPC.transferfromaddress(
            asset_name,
            admin_addr,
            1,
            system_addr,
            '',
            0,
            admin_addr,
            admin_addr,
        )
        report['ok'] = True
        report['txid'] = txid
    except Exception as exc:
        report['ok'] = False
        report['error'] = str(exc)
    finally:
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
