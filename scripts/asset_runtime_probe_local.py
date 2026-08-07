import json
import os
import sys
from datetime import datetime, timezone

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
    admin = User.objects.get(username='admin')
    system = User.objects.get(username='system')

    admin_wallet = Wallet(admin.user_wallet.entropy, admin.user_wallet.passphrase, network_mode='testnet')
    system_wallet = Wallet(system.user_wallet.entropy, system.user_wallet.passphrase, network_mode='testnet')

    admin_addr = admin_wallet.get_address(0)
    system_addr = system_wallet.get_address(0)

    asset_name = f"TST{datetime.now(timezone.utc).strftime('%m%d%H%M%S')}"

    report = {
        'admin_address': admin_addr,
        'system_address': system_addr,
        'asset_name_attempt': asset_name,
        'endpoint_mode': 'local',
    }

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('local')

    try:
        try:
            issue_result = RPC.issue(asset_name, 1000, admin_addr, admin_addr, 0, True, False, '')
            report['issue_ok'] = True
            report['issue_result'] = issue_result
        except Exception as exc:
            report['issue_ok'] = False
            report['issue_error'] = str(exc)

        try:
            transfer_result = RPC.transferfromaddress(
                'NOTAREALASSET',
                admin_addr,
                1,
                system_addr,
                '',
                0,
                admin_addr,
                admin_addr,
            )
            report['transferfromaddress_ok'] = True
            report['transferfromaddress_result'] = transfer_result
        except Exception as exc:
            report['transferfromaddress_ok'] = False
            report['transferfromaddress_error'] = str(exc)

    finally:
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
