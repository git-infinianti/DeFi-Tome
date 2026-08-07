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


def main():
    if len(sys.argv) < 3:
        raise SystemExit('Usage: inspect_issue_tx_local.py <TXID> <ASSET_NAME>')

    txid = sys.argv[1]
    asset_name = sys.argv[2]

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('local')

    report = {
        'txid': txid,
        'asset_name': asset_name,
    }

    try:
        try:
            report['getrawtransaction'] = RPC.getrawtransaction(txid, True)
        except Exception as exc:
            report['getrawtransaction_error'] = str(exc)

        try:
            report['gettransaction'] = RPC.gettransaction(txid)
        except Exception as exc:
            report['gettransaction_error'] = str(exc)

        try:
            report['getassetdata'] = RPC.getassetdata(asset_name)
        except Exception as exc:
            report['getassetdata_error'] = str(exc)
    finally:
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
