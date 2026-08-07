import json
import os
import sys

import requests

REPO_TOME = '/Users/chiefton/Documents/GitHub/DeFiTome/Tome'
if REPO_TOME not in sys.path:
    sys.path.insert(0, REPO_TOME)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tome.settings')

import django

django.setup()

from django.conf import settings
from django.contrib.auth.models import User
from Wallet.wallet import Wallet


def build_local_url():
    url = getattr(settings, 'RPC_TESTNET_URL', None)
    if url:
        return str(url).strip()

    host = getattr(settings, 'RPC_TESTNET_HOST', None) or '127.0.0.1'
    port = getattr(settings, 'RPC_TESTNET_PORT', None) or '18819'
    scheme = getattr(settings, 'RPC_TESTNET_SCHEME', 'http')
    path = str(getattr(settings, 'RPC_TESTNET_PATH', '/') or '/').strip()
    if not path.startswith('/'):
        path = f'/{path}'
    return f'{scheme}://{host}:{port}{path}'


def rpc_call(url, auth, method, params):
    payload = {
        'jsonrpc': '1.0',
        'id': 'diag-local-transfer',
        'method': method,
        'params': params,
    }

    try:
        response = requests.post(url, json=payload, timeout=15, auth=auth)
    except Exception as exc:
        return {
            'ok': False,
            'request_error': str(exc),
        }

    body_json = None
    body_text = response.text
    try:
        body_json = response.json()
    except Exception:
        pass

    return {
        'ok': response.status_code == 200 and isinstance(body_json, dict) and not body_json.get('error'),
        'status_code': response.status_code,
        'reason': response.reason,
        'json': body_json,
        'text': body_text[:4000],
    }


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: diagnose_local_transfer_error.py <ASSET_NAME>')

    asset_name = sys.argv[1]

    admin = User.objects.get(username='admin')
    system = User.objects.get(username='system')

    admin_wallet = Wallet(admin.user_wallet.entropy, admin.user_wallet.passphrase, network_mode='testnet')
    system_wallet = Wallet(system.user_wallet.entropy, system.user_wallet.passphrase, network_mode='testnet')

    admin_addr = admin_wallet.get_address(0)
    system_addr = system_wallet.get_address(0)

    url = build_local_url()
    auth = (
        getattr(settings, 'RPC_TESTNET_USER', None),
        getattr(settings, 'RPC_TESTNET_PASSWORD', None),
    )

    report = {
        'url': url,
        'rpc_user_set': bool(auth[0]),
        'rpc_password_set': bool(auth[1]),
        'asset_name': asset_name,
        'admin_address': admin_addr,
        'system_address': system_addr,
        'calls': {},
    }

    report['calls']['help_transferfromaddress'] = rpc_call(url, auth, 'help', ['transferfromaddress'])
    report['calls']['listassetbalancesbyaddress_admin'] = rpc_call(url, auth, 'listassetbalancesbyaddress', [admin_addr])
    report['calls']['getassetdata'] = rpc_call(url, auth, 'getassetdata', [asset_name])
    report['calls']['transferfromaddress'] = rpc_call(
        url,
        auth,
        'transferfromaddress',
        [asset_name, admin_addr, 1, system_addr, '', 0, admin_addr, admin_addr],
    )

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
