from decimal import Decimal
from datetime import datetime, timezone
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
from Wallet.models import WalletAddress
from Wallet.wallet import Wallet
from Wallet.rpc import (
    create_and_send_asset_transfer_transaction,
    create_and_send_evr_transaction,
    create_and_send_issue_asset_transaction,
)
from Tome.rpc_client import (
    RPC,
    clear_active_network_mode,
    clear_active_rpc_endpoint_mode,
    set_active_network_mode,
    set_active_rpc_endpoint_mode,
)


def ensure_testnet_address(user):
    row = (
        WalletAddress.objects.filter(
            wallet=user.user_wallet,
            network_mode='testnet',
            is_change=False,
        )
        .order_by('account', 'index')
        .first()
    )
    if row:
        return row.address, row.wif, False

    wallet = Wallet(user.user_wallet.entropy, user.user_wallet.passphrase, network_mode='testnet')
    addr = wallet.get_address(0)
    wif = wallet.get_wif(0)
    created = WalletAddress.objects.create(
        wallet=user.user_wallet,
        network_mode='testnet',
        address=addr,
        wif=wif,
        account=0,
        index=0,
        is_change=False,
    )
    return created.address, created.wif, True


def _coin_utxo_satoshis(address):
    utxos = RPC.getaddressutxos({'addresses': [address]})
    if not isinstance(utxos, list):
        return 0

    total = 0
    for utxo in utxos:
        asset_name = utxo.get('assetName') or utxo.get('assetname') or utxo.get('asset')
        if asset_name and str(asset_name).upper() != 'EVR':
            continue
        total += int(utxo.get('satoshis', 0))
    return total


def find_spendable_testnet_address(user, min_coin_sats=1, max_scan=200):
    wallet = Wallet(user.user_wallet.entropy, user.user_wallet.passphrase, network_mode='testnet')

    best = None
    for index in range(int(max_scan)):
        address = wallet.get_address(index)
        wif = wallet.get_wif(index)

        try:
            spendable_sats = _coin_utxo_satoshis(address)
        except Exception:
            continue

        if best is None or spendable_sats > best['coin_utxo_sats']:
            best = {
                'index': index,
                'address': address,
                'wif': wif,
                'coin_utxo_sats': spendable_sats,
            }

        if spendable_sats >= int(min_coin_sats):
            WalletAddress.objects.get_or_create(
                wallet=user.user_wallet,
                network_mode='testnet',
                account=0,
                index=index,
                is_change=False,
                defaults={
                    'address': address,
                    'wif': wif,
                },
            )
            return {
                'found': True,
                'index': index,
                'address': address,
                'wif': wif,
                'coin_utxo_sats': spendable_sats,
            }

    return {
        'found': False,
        'best': best,
    }


def _redact_scan_result(scan_result):
    if not isinstance(scan_result, dict):
        return scan_result

    clone = dict(scan_result)
    if 'wif' in clone:
        clone['wif'] = '<redacted>'

    best = clone.get('best')
    if isinstance(best, dict) and 'wif' in best:
        best_clone = dict(best)
        best_clone['wif'] = '<redacted>'
        clone['best'] = best_clone

    return clone


def main():
    force_public_only = os.getenv('EVR_LIVE_TEST_FORCE_PUBLIC', '1').strip().lower() not in ('0', 'false', 'no')

    report = {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'network': 'testnet',
        'endpoint_mode': 'public_only_forced' if force_public_only else 'routed_mode',
        'health': {},
        'accounts': {},
        'transactions': [],
        'errors': [],
    }

    original_get_backends = RPC._get_backends

    if force_public_only:
        # Force the routed client to use only public RPC, never local fallback.
        RPC._get_backends = lambda network_mode, rpc_endpoint_mode: [
            ('public', RPC._get_public_client(network_mode))
        ]

    set_active_network_mode('testnet')
    set_active_rpc_endpoint_mode('public')

    try:
        for method_name, fn in (
            ('getblockchaininfo', lambda: RPC.getblockchaininfo()),
            ('getbestblockhash', lambda: RPC.getbestblockhash()),
            ('getmempoolinfo', lambda: RPC.getmempoolinfo()),
            ('help', lambda: RPC.help()),
        ):
            try:
                result = fn()
                if method_name == 'help':
                    report['health'][method_name] = {'ok': True, 'length': len(str(result))}
                else:
                    report['health'][method_name] = {'ok': True}
                    if method_name == 'getblockchaininfo' and isinstance(result, dict):
                        report['health'][method_name]['chain'] = result.get('chain')
                        report['health'][method_name]['blocks'] = result.get('blocks')
            except Exception as exc:
                report['health'][method_name] = {'ok': False, 'error': str(exc)}

        admin = User.objects.get(username='admin')
        system = User.objects.get(username='system')

        admin_addr, admin_wif, admin_created = ensure_testnet_address(admin)
        system_addr, system_wif, system_created = ensure_testnet_address(system)

        report['accounts']['admin'] = {
            'address': admin_addr,
            'address_created_for_testnet': admin_created,
            'validateaddress': RPC.validateaddress(admin_addr),
        }
        report['accounts']['system'] = {
            'address': system_addr,
            'address_created_for_testnet': system_created,
            'validateaddress': RPC.validateaddress(system_addr),
        }

        admin_balance_data = RPC.getaddressbalance({'addresses': [admin_addr]})
        system_balance_data = RPC.getaddressbalance({'addresses': [system_addr]})

        admin_sats = int((admin_balance_data or {}).get('balance', 0))
        system_sats = int((system_balance_data or {}).get('balance', 0))

        report['accounts']['admin']['balance_sats_before'] = admin_sats
        report['accounts']['system']['balance_sats_before'] = system_sats

        admin_spendable = find_spendable_testnet_address(admin, min_coin_sats=1_200_000)
        report['accounts']['admin']['spendable_scan'] = _redact_scan_result(admin_spendable)

        system_spendable_before = find_spendable_testnet_address(system, min_coin_sats=1)
        report['accounts']['system']['spendable_scan_before'] = _redact_scan_result(system_spendable_before)

        evr_send_amount = Decimal('0.01')
        relay_fee_evr = Decimal('0.01')
        if admin_spendable.get('found'):
            admin_source_addr = admin_spendable['address']
            admin_source_wif = admin_spendable['wif']

            try:
                tx = create_and_send_evr_transaction(
                    from_address=admin_source_addr,
                    to_address=system_addr,
                    amount_evr=evr_send_amount,
                    change_address=admin_source_addr,
                    fee_evr=relay_fee_evr,
                    wif_keys=[admin_source_wif],
                )
                evr_txid = tx['txid']

                verification = {
                    'txid': evr_txid,
                    'destination': system_addr,
                    'expected_amount_evr': str(evr_send_amount),
                    'source_address': admin_source_addr,
                }
                try:
                    raw_verbose = RPC.getrawtransaction(evr_txid, True)
                    found = False
                    for vout in raw_verbose.get('vout', []):
                        value = Decimal(str(vout.get('value', '0')))
                        addrs = (((vout.get('scriptPubKey') or {}).get('addresses')) or [])
                        if system_addr in addrs and value == evr_send_amount:
                            found = True
                            break
                    verification['verified_by_getrawtransaction'] = found
                except Exception as exc:
                    verification['verified_by_getrawtransaction'] = False
                    verification['getrawtransaction_error'] = str(exc)

                try:
                    mempool_rows = RPC.getaddressmempool({'addresses': [system_addr]})
                    verification['seen_in_system_address_mempool'] = any(
                        row.get('txid') == evr_txid for row in (mempool_rows or [])
                    )
                except Exception as exc:
                    verification['seen_in_system_address_mempool'] = False
                    verification['getaddressmempool_error'] = str(exc)

                report['transactions'].append(
                    {
                        'type': 'evr_transfer',
                        'from': admin_source_addr,
                        'to': system_addr,
                        'amount_evr': str(evr_send_amount),
                        'txid': evr_txid,
                        'verification': verification,
                    }
                )
            except Exception as exc:
                report['errors'].append(f'EVR transfer admin->system failed: {exc}')
        else:
            report['errors'].append('No spendable admin testnet address found for EVR transfer.')

        admin_balance_after_send = RPC.getaddressbalance({'addresses': [admin_addr]})
        admin_sats_after_send = int((admin_balance_after_send or {}).get('balance', 0))
        report['accounts']['admin']['balance_sats_post_evr_send'] = admin_sats_after_send

        burn_requirement_sats = 50_010_000_000
        asset_name = f"TST{datetime.now(timezone.utc).strftime('%m%d%H%M%S')}"

        admin_asset_source = find_spendable_testnet_address(admin, min_coin_sats=burn_requirement_sats)
        report['accounts']['admin']['asset_issue_source_scan'] = _redact_scan_result(admin_asset_source)

        if admin_asset_source.get('found'):
            asset_source_addr = admin_asset_source['address']
            asset_source_wif = admin_asset_source['wif']
            try:
                issue_tx = create_and_send_issue_asset_transaction(
                    from_address=asset_source_addr,
                    issuer_address=asset_source_addr,
                    asset_name=asset_name,
                    asset_quantity=1000,
                    units=0,
                    reissuable=True,
                    has_ipfs=False,
                    fee_evr=relay_fee_evr,
                    wif_keys=[asset_source_wif],
                )
                issue_txid = issue_tx['txid']
                report['transactions'].append(
                    {
                        'type': 'asset_issue',
                        'asset': asset_name,
                        'issuer': asset_source_addr,
                        'txid': issue_txid,
                    }
                )

                try:
                    transfer_tx = create_and_send_asset_transfer_transaction(
                        from_address=asset_source_addr,
                        to_address=system_addr,
                        asset_name=asset_name,
                        asset_quantity=1,
                        change_address=asset_source_addr,
                        fee_evr=relay_fee_evr,
                        wif_keys=[asset_source_wif],
                    )
                    transfer_txid = transfer_tx['txid']

                    transfer_verification = {
                        'txid': transfer_txid,
                        'asset': asset_name,
                        'to': system_addr,
                    }
                    try:
                        mempool_rows = RPC.getaddressmempool({'addresses': [system_addr]})
                        transfer_verification['seen_in_system_address_mempool'] = any(
                            row.get('txid') == transfer_txid for row in (mempool_rows or [])
                        )
                    except Exception as exc:
                        transfer_verification['seen_in_system_address_mempool'] = False
                        transfer_verification['getaddressmempool_error'] = str(exc)

                    report['transactions'].append(
                        {
                            'type': 'asset_transfer',
                            'asset': asset_name,
                            'from': asset_source_addr,
                            'to': system_addr,
                            'quantity': '1',
                            'txid': transfer_txid,
                            'verification': transfer_verification,
                        }
                    )
                except Exception as exc:
                    report['errors'].append(f'Asset transfer {asset_name} admin->system failed: {exc}')

            except Exception as exc:
                report['errors'].append(f'Asset issuance {asset_name} failed: {exc}')
        else:
            report['errors'].append(
                'No single spendable admin testnet address has >=500.1 EVR required for root asset issuance burn.'
            )

        system_balance_now = RPC.getaddressbalance({'addresses': [system_addr]})
        system_sats_now = int((system_balance_now or {}).get('balance', 0))
        report['accounts']['system']['balance_sats_after_receive'] = system_sats_now

        system_spendable_after = find_spendable_testnet_address(system, min_coin_sats=700_000)
        report['accounts']['system']['spendable_scan_after'] = _redact_scan_result(system_spendable_after)

        if system_spendable_after.get('found'):
            source = system_spendable_after['address']
            source_wif = system_spendable_after['wif']
            try:
                back_tx = create_and_send_evr_transaction(
                    from_address=source,
                    to_address=admin_addr,
                    amount_evr=Decimal('0.005'),
                    change_address=source,
                    fee_evr=relay_fee_evr,
                    wif_keys=[source_wif],
                )
                report['transactions'].append(
                    {
                        'type': 'evr_transfer_reverse',
                        'from': source,
                        'to': admin_addr,
                        'amount_evr': '0.005',
                        'txid': back_tx['txid'],
                    }
                )
            except Exception as exc:
                report['errors'].append(f'EVR transfer system->admin failed: {exc}')
        else:
            report['errors'].append('System has no spendable testnet address for reverse EVR transfer.')

    except Exception as exc:
        report['errors'].append(f'Unhandled test execution error: {exc}')
    finally:
        RPC._get_backends = original_get_backends
        clear_active_network_mode()
        clear_active_rpc_endpoint_mode()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
