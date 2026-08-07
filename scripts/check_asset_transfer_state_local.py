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


def safe_call(fn):
    try:
        return {'ok': True, 'result': fn()}
    except Exception as exc:
        return {'ok': False, 'error': str(exc)}


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: check_asset_transfer_state_local.py <ASSET_NAME> [TXID1] [TXID2] ...')

    asset_name = sys.argv[1]
    txids = sys.argv[2:]

    admin = User.objects.get(username='admin')
    system = User.objects.get(username='system')

    admin_wallet = Wallet(admin.user_wallet.entropy, admin.user_wallet.passphrase, network_mode='testnet')
    system_wallet = Wallet(system.user_wallet.entropy, system.user_wallet.passphrase, network_mode='testnet')

    admin_addr = admin_wallet.get_address(0)
    system_addr = system_wallet.get_address(0)

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('local')

    report = {
        'asset_name': asset_name,
        'admin_address': admin_addr,
        'system_address': system_addr,
        'checks': {},
    }

    try:
        report['checks']['getrawmempool'] = safe_call(lambda: RPC.getrawmempool())
        report['checks']['getassetdata'] = safe_call(lambda: RPC.getassetdata(asset_name))
        report['checks']['admin_asset_balances'] = safe_call(lambda: RPC.listassetbalancesbyaddress(admin_addr))
        report['checks']['system_asset_balances'] = safe_call(lambda: RPC.listassetbalancesbyaddress(system_addr))

        tx_checks = {}
        for txid in txids:
            tx_checks[txid] = {
                'getrawtransaction': safe_call(lambda txid=txid: RPC.getrawtransaction(txid, True)),
                'gettransaction': safe_call(lambda txid=txid: RPC.gettransaction(txid)),
            }
        report['checks']['txids'] = tx_checks

        mempool = report['checks']['getrawmempool']
        if mempool.get('ok') and isinstance(mempool.get('result'), list):
            mempool_set = set(mempool['result'])
            report['checks']['txid_in_mempool'] = {txid: (txid in mempool_set) for txid in txids}

    finally:
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
