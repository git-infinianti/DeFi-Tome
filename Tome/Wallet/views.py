from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.db import OperationalError, transaction
from django.urls import reverse
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from collections import OrderedDict
from datetime import datetime
import hashlib
import hmac
import time
import requests
from .models import UserWallet, WalletAddress, WalletProfile, SafeTradeCredentials, TrackedAsset
from .wallet import Wallet
from .asset_tracking import sync_tracked_assets
from .rpc import RPC, create_and_send_evr_transaction, create_and_send_asset_transfer_transaction
from hdwallet.entropies import BIP39Entropy
from hdwallet.derivations import BIP44Derivation, CHANGES
from hdwallet import cryptocurrencies
from Tome.rpc_client import get_current_network_mode
from Tome.qr import build_qr_data_uri


SAFETRADE_BASE_URL = 'https://safe.trade/api/v2'


def _active_network_mode():
    return get_current_network_mode()


def _wallet_for_network(user_wallet):
    return Wallet(
        user_wallet.entropy,
        user_wallet.passphrase,
        network_mode=_active_network_mode(),
    )


def _get_stored_network_balance(user_wallet):
    network_mode = _active_network_mode()
    if network_mode == 'mainnet':
        return user_wallet.evr_liquidity_mainnet or Decimal('0')
    return user_wallet.evr_liquidity_testnet or Decimal('0')


def _set_stored_network_balance(user_wallet, balance, updated_at=None):
    network_mode = _active_network_mode()
    balance_value = Decimal(str(balance or 0))
    update_time = updated_at or timezone.now()

    if network_mode == 'mainnet':
        user_wallet.evr_liquidity_mainnet = balance_value
        user_wallet.last_balance_update_mainnet = update_time
        # Keep legacy field aligned for backward compatibility.
        user_wallet.evr_liquidity = balance_value
        user_wallet.last_balance_update = update_time
    else:
        user_wallet.evr_liquidity_testnet = balance_value
        user_wallet.last_balance_update_testnet = update_time

    user_wallet.save()


def _sync_user_evr_balance(user_wallet):
    """
    Sync user's EVR balance from blockchain using getaddressbalance RPC command.
    
    Args:
        user_wallet: UserWallet instance to update
        
    Returns:
        Decimal: The balance amount, or None if failed
        
    Side effects:
        - Updates user_wallet.evr_liquidity with the balance from the RPC
        - Updates user_wallet.last_balance_update timestamp
        - Saves changes to database
    """
    try:
        address = _get_user_primary_address(user_wallet.user)
        if not address:
            return None
        
        # Call getaddressbalance RPC command
        balance_data = RPC.getaddressbalance(address)
        
        # Extract balance from response: {"balance": 0, "received": 0}
        if isinstance(balance_data, dict) and 'balance' in balance_data:
            balance = Decimal(str(balance_data['balance']))
            _set_stored_network_balance(user_wallet, balance, timezone.now())
            return balance
        else:
            print(f"Unexpected balance response format: {balance_data}")
            return None
            
    except Exception as e:
        print(f"Error syncing balance for user_id {user_wallet.user_id}: {str(e)}")
        return None


def _get_user_primary_address(user):
    """Get the user's primary wallet address for RPC asset balance checks."""
    user_wallet = getattr(user, 'user_wallet', None)
    if not user_wallet:
        return None

    main_profile = _get_or_create_main_wallet_profile(user)
    if main_profile:
        return main_profile.address.address

    return None


def _ensure_external_wallet_address(user_wallet, index):
    network_mode = _active_network_mode()
    address_record = WalletAddress.objects.filter(
        wallet=user_wallet,
        network_mode=network_mode,
        account=0,
        index=index,
        is_change=False,
    ).first()

    if address_record:
        return address_record

    wallet_instance = _wallet_for_network(user_wallet)
    address = wallet_instance.get_address(index=index)
    wif = wallet_instance.get_wif(index=index)
    RPC.importprivkey(wif, str(user_wallet.entropy), False)
    address_record, _created = WalletAddress.objects.get_or_create(
        wallet=user_wallet,
        network_mode=network_mode,
        account=0,
        index=index,
        is_change=False,
        defaults={
            'address': address,
            'wif': wif,
        },
    )
    return address_record


def _ensure_change_wallet_address(user_wallet, index=0):
    network_mode = _active_network_mode()
    address_record = WalletAddress.objects.filter(
        wallet=user_wallet,
        network_mode=network_mode,
        account=0,
        index=index,
        is_change=True,
    ).first()

    if address_record:
        return address_record

    wallet_instance = _wallet_for_network(user_wallet)
    address = wallet_instance.get_change_address(index=index)
    wif = wallet_instance.get_change_wif(index=index)
    address_record, _created = WalletAddress.objects.get_or_create(
        wallet=user_wallet,
        network_mode=network_mode,
        account=0,
        index=index,
        is_change=True,
        defaults={
            'address': address,
            'wif': wif,
        },
    )
    return address_record


def _get_or_create_main_wallet_profile(user):
    user_wallet = getattr(user, 'user_wallet', None)
    if not user_wallet:
        return None

    network_mode = _active_network_mode()
    main_profile = WalletProfile.objects.select_related('address').filter(
        wallet=user_wallet,
        network_mode=network_mode,
        is_main=True,
    ).first()
    if main_profile:
        return main_profile

    fallback_profile = WalletProfile.objects.select_related('address').filter(
        wallet=user_wallet,
        network_mode=network_mode,
    ).order_by('created_at', 'id').first()
    if fallback_profile:
        WalletProfile.objects.filter(pk=fallback_profile.pk).update(is_main=True)
        fallback_profile.is_main = True
        return fallback_profile

    address_record = WalletAddress.objects.filter(
        wallet=user_wallet,
        network_mode=network_mode,
        is_change=False
    ).order_by('account', 'index').first()

    try:
        if address_record is None:
            address_record = _ensure_external_wallet_address(user_wallet, index=0)

        profile, _created = WalletProfile.objects.get_or_create(
            wallet=user_wallet,
            network_mode=network_mode,
            address=address_record,
            defaults={
                'name': 'Main',
                'is_main': True,
            },
        )
        if not profile.is_main:
            WalletProfile.objects.filter(
                wallet=user_wallet,
                network_mode=network_mode,
                is_main=True,
            ).exclude(pk=profile.pk).update(is_main=False)
            profile.is_main = True
            profile.save()
        return profile
    except Exception:
        return None


def _get_wallet_profiles(user):
    user_wallet = getattr(user, 'user_wallet', None)
    if not user_wallet:
        return WalletProfile.objects.none()

    _get_or_create_main_wallet_profile(user)
    return WalletProfile.objects.select_related('address').filter(
        wallet=user_wallet,
        network_mode=_active_network_mode(),
    ).order_by('-is_main', 'address__index', 'created_at', 'id')


def _next_external_address_index(user_wallet):
    highest_index = WalletAddress.objects.filter(
        wallet=user_wallet,
        network_mode=_active_network_mode(),
        account=0,
        is_change=False,
    ).order_by('-index').values_list('index', flat=True).first()
    if highest_index is None:
        return 0
    return int(highest_index) + 1


def _redirect_send_funds_to(tab_name):
    return redirect(f"{reverse('send_funds')}#{tab_name}")


def _create_wallet_profile(request):
    user_wallet = getattr(request.user, 'user_wallet', None)
    if not user_wallet:
        messages.error(request, 'No wallet found to create a profile.')
        return _redirect_send_funds_to('profiles')

    profile_name = str(request.POST.get('profile_name', '') or '').strip()
    if not profile_name:
        messages.error(request, 'Profile name is required.')
        return _redirect_send_funds_to('profiles')

    if len(profile_name) > 100:
        messages.error(request, 'Profile name must be 100 characters or less.')
        return _redirect_send_funds_to('profiles')

    network_mode = _active_network_mode()
    if WalletProfile.objects.filter(
        wallet=user_wallet,
        network_mode=network_mode,
        name__iexact=profile_name,
    ).exists():
        messages.error(request, 'A profile with that name already exists on this network.')
        return _redirect_send_funds_to('profiles')

    try:
        with transaction.atomic():
            next_index = _next_external_address_index(user_wallet)
            address_record = _ensure_external_wallet_address(user_wallet, next_index)
            profile = WalletProfile.objects.create(
                wallet=user_wallet,
                address=address_record,
                network_mode=network_mode,
                name=profile_name,
                is_main=not WalletProfile.objects.filter(
                    wallet=user_wallet,
                    network_mode=network_mode,
                    is_main=True,
                ).exists(),
            )
    except (ValidationError, IntegrityError) as exc:
        messages.error(request, f'Unable to create wallet profile: {exc}')
        return _redirect_send_funds_to('profiles')
    except Exception as exc:
        messages.error(request, f'Unable to derive and import a new wallet address: {exc}')
        return _redirect_send_funds_to('profiles')

    messages.success(request, f'Profile "{profile.name}" created for address {profile.address.address}.')
    return _redirect_send_funds_to('profiles')


def _set_main_wallet_profile(request):
    user_wallet = getattr(request.user, 'user_wallet', None)
    if not user_wallet:
        messages.error(request, 'No wallet found to update a profile.')
        return _redirect_send_funds_to('profiles')

    profile_id = str(request.POST.get('profile_id', '') or '').strip()
    if not profile_id:
        messages.error(request, 'Profile selection is required.')
        return _redirect_send_funds_to('profiles')

    profile = WalletProfile.objects.select_related('address').filter(
        wallet=user_wallet,
        network_mode=_active_network_mode(),
        pk=profile_id,
    ).first()
    if not profile:
        messages.error(request, 'Selected profile was not found on the active network.')
        return _redirect_send_funds_to('profiles')

    WalletProfile.objects.filter(
        wallet=user_wallet,
        network_mode=profile.network_mode,
        is_main=True,
    ).exclude(pk=profile.pk).update(is_main=False)
    if not profile.is_main:
        profile.is_main = True
        profile.save()

    messages.success(request, f'"{profile.name}" is now your main wallet profile.')
    return _redirect_send_funds_to('profiles')


def _derive_user_wif_for_address(user, address):
    """Derive the signing WIF for an address from user entropy at runtime."""
    user_wallet = getattr(user, 'user_wallet', None)
    if not user_wallet:
        raise Exception('No wallet found for user.')

    wallet_instance = _wallet_for_network(user_wallet)
    try:
        return wallet_instance.get_wif_for_address(address)
    except ValueError as exc:
        raise Exception(f'Unable to derive signing key for address {address}: {str(exc)}')


def _get_user_asset_balances(user, sync_tracking=True):
    """Return a dict of asset balances for the user's primary address."""
    address = _get_user_primary_address(user)
    if not address:
        return {}, 'no_wallet'

    try:
        balances = RPC.listassetbalancesbyaddress(address)
    except Exception as e:
        return {}, f'rpc_error: {str(e)}'

    if not isinstance(balances, dict):
        return {}, 'invalid_response'

    asset_balances = {}
    for symbol, amount in balances.items():
        if not symbol or not isinstance(symbol, str):
            continue
        try:
            amount_decimal = Decimal(str(amount))
        except (ValueError, InvalidOperation):
            continue
        if amount_decimal > 0:
            asset_balances[symbol.upper()] = amount_decimal

    if sync_tracking:
        try:
            sync_tracked_assets(user, asset_balances)
        except OperationalError as exc:
            # Asset tracking sync is non-critical for request success.
            if 'database is locked' not in str(exc).lower():
                raise
    return asset_balances, None


def _format_asset_amount(amount):
    """Format Decimal amounts by trimming trailing zeros or flooring to int if whole."""
    amount_str = format(amount, 'f')
    if '.' in amount_str:
        amount_str = amount_str.rstrip('0').rstrip('.')
    return amount_str or '0'


def _amount_quantum_for_units(units):
    normalized_units = max(0, min(8, int(units or 0)))
    return Decimal('1').scaleb(-normalized_units)


def _step_string_for_units(units):
    quantum = _amount_quantum_for_units(units)
    return format(quantum, 'f')


def _get_asset_units(symbol):
    normalized_symbol = str(symbol or '').strip().upper()
    if normalized_symbol == 'EVR':
        return 8
    if normalized_symbol.endswith('!'):
        return 0

    try:
        asset_data = RPC.getassetdata(normalized_symbol)
    except Exception:
        asset_data = None

    if isinstance(asset_data, dict):
        try:
            return max(0, min(8, int(asset_data.get('units', 8))))
        except (TypeError, ValueError):
            pass

    tracked_asset = TrackedAsset.objects.filter(
        symbol=normalized_symbol,
        network_mode=_active_network_mode(),
    ).only('units').first()
    if tracked_asset is not None:
        return max(0, min(8, int(tracked_asset.units or 0)))

    try:
        return max(0, min(8, int(asset_data.get('units', 8))))
    except (AttributeError, TypeError, ValueError):
        return 8


def _normalize_amount_for_units(raw_amount, units):
    try:
        amount = Decimal(str(raw_amount).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Invalid amount specified.')

    if amount <= 0:
        raise ValueError('Amount must be greater than 0.')

    quantum = _amount_quantum_for_units(units)
    normalized = amount.quantize(quantum, rounding=ROUND_DOWN)
    if normalized != amount:
        if int(units or 0) == 0:
            raise ValueError('This asset is indivisible and must be sent as a whole number.')
        raise ValueError(f'Amount exceeds the allowed precision for this asset. Maximum decimal places: {int(units)}.')

    return normalized


def _get_user_wallet_addresses(user, include_change=True):
    user_wallet = getattr(user, 'user_wallet', None)
    if not user_wallet:
        return []

    addresses = OrderedDict()
    primary_address = _get_user_primary_address(user)
    if primary_address:
        addresses[primary_address] = None

    queryset = WalletAddress.objects.filter(
        wallet=user_wallet,
        network_mode=_active_network_mode(),
    )
    if not include_change:
        queryset = queryset.filter(is_change=False)

    for address in queryset.order_by('is_change', 'account', 'index').values_list('address', flat=True):
        normalized_address = str(address or '').strip()
        if normalized_address:
            addresses[normalized_address] = None

    return list(addresses.keys())


def _coerce_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _format_evr_delta(satoshis):
    evr_amount = (Decimal(int(satoshis)) * Decimal('1e-8')).quantize(Decimal('0.00000001'))
    return f'{evr_amount:+.8f} EVR'


def _format_signed_asset_delta(amount):
    sign = '+' if amount > 0 else '-'
    return f'{sign}{_format_asset_amount(abs(amount))}'


def _classify_transaction_direction(evr_delta_sats, asset_deltas):
    has_positive = evr_delta_sats > 0 or any(amount > 0 for amount in asset_deltas.values())
    has_negative = evr_delta_sats < 0 or any(amount < 0 for amount in asset_deltas.values())

    if has_positive and has_negative:
        return 'mixed'
    if has_positive:
        return 'received'
    if has_negative:
        return 'sent'
    return 'neutral'


def _build_transaction_summaries(addresses, txids):
    summaries = {
        txid: {
            'evr_delta_sats': 0,
            'asset_deltas': OrderedDict(),
        }
        for txid in txids
    }

    try:
        deltas = RPC.getaddressdeltas({'addresses': list(addresses)})
    except Exception as exc:
        return summaries, str(exc)

    if not isinstance(deltas, list):
        return summaries, f'Unexpected transaction delta response: {deltas}'

    target_txids = set(txids)
    for delta in deltas:
        txid = str(delta.get('txid') or '').strip()
        if txid not in target_txids:
            continue

        summary = summaries[txid]
        satoshis = delta.get('satoshis')
        if satoshis is not None:
            try:
                summary['evr_delta_sats'] += int(satoshis)
            except (TypeError, ValueError):
                pass

        asset_name = (
            delta.get('assetName')
            or delta.get('assetname')
            or delta.get('asset')
        )
        if not asset_name:
            continue

        asset_delta = None
        for key in ('assetAmount', 'amount', 'quantity'):
            if key in delta:
                asset_delta = _coerce_decimal(delta.get(key))
                if asset_delta is not None:
                    break

        if asset_delta is None:
            continue

        existing_amount = summary['asset_deltas'].get(asset_name, Decimal('0'))
        summary['asset_deltas'][asset_name] = existing_amount + asset_delta

    return summaries, None


def _normalize_transaction_time(tx_detail):
    timestamp = tx_detail.get('blocktime') or tx_detail.get('time')
    if not timestamp:
        return None

    try:
        naive_time = datetime.fromtimestamp(int(timestamp))
    except (TypeError, ValueError, OSError):
        return None

    aware_time = timezone.make_aware(naive_time, timezone.get_current_timezone())
    return timezone.localtime(aware_time)


def _build_wallet_transaction_rows(txids, tx_summaries):
    transactions = []
    detail_errors = []

    for txid in txids:
        tx_detail = {}
        try:
            tx_response = RPC.getrawtransaction(txid, True)
            if isinstance(tx_response, dict):
                tx_detail = tx_response
        except Exception as exc:
            detail_errors.append(f'{txid}: {str(exc)}')

        summary = tx_summaries.get(txid, {'evr_delta_sats': 0, 'asset_deltas': OrderedDict()})
        direction = _classify_transaction_direction(summary['evr_delta_sats'], summary['asset_deltas'])

        asset_changes = []
        for asset_name, amount in summary['asset_deltas'].items():
            if amount == 0:
                continue
            asset_changes.append({
                'asset_name': asset_name,
                'amount': amount,
                'amount_display': f'{_format_signed_asset_delta(amount)} {asset_name}',
            })

        transactions.append({
            'txid': txid,
            'direction': direction,
            'direction_label': direction.replace('_', ' ').title(),
            'confirmations': tx_detail.get('confirmations'),
            'blockhash': tx_detail.get('blockhash'),
            'blocktime': _normalize_transaction_time(tx_detail),
            'size': tx_detail.get('size'),
            'evr_delta_sats': summary['evr_delta_sats'],
            'evr_delta_display': _format_evr_delta(summary['evr_delta_sats']) if summary['evr_delta_sats'] else None,
            'asset_changes': asset_changes,
        })

    return transactions, detail_errors


def _build_transaction_limit_options(selected_limit):
    selected_token = 'all' if selected_limit is None else str(selected_limit)
    options = [
        {'value': 'all', 'label': 'All', 'is_selected': selected_token == 'all'},
    ]
    for option in (25, 50, 100, 250):
        options.append({
            'value': str(option),
            'label': f'Latest {option}',
            'is_selected': selected_token == str(option),
        })
    return options


def _build_load_more_limit_options(selected_limit):
    if selected_limit is None:
        return []

    options = []
    for option in _build_transaction_limit_options(selected_limit):
        if option['value'] == 'all':
            options.append(option)
            continue

        try:
            option_value = int(option['value'])
        except (TypeError, ValueError):
            continue

        if option_value > selected_limit:
            options.append(option)
    return options


def _fetch_safetrade_member_info(api_key, api_secret):
    """Fetch SafeTrade member profile using signed auth headers."""
    nonce = str(int(time.time() * 1000))
    payload = f"{nonce}{api_key}".encode('utf-8')
    signature = hmac.new(
        api_secret.encode('utf-8'),
        payload,
        hashlib.sha256,
    ).hexdigest()

    headers = {
        'X-Auth-Apikey': api_key,
        'X-Auth-Nonce': nonce,
        'X-Auth-Signature': signature,
    }

    try:
        response = requests.get(
            f'{SAFETRADE_BASE_URL}/trade/account/members/me',
            headers=headers,
            timeout=12,
        )
    except requests.RequestException as exc:
        return None, f'Unable to reach SafeTrade: {str(exc)}'

    response_payload = None
    if response.status_code >= 400:
        try:
            response_payload = response.json()
        except ValueError:
            response_payload = None

    if response.status_code == 401:
        if isinstance(response_payload, dict):
            errors = response_payload.get('errors')
            if isinstance(errors, list) and 'authz.apikey_untrusted_ip' in errors:
                server_ip = _get_server_public_ip()
                ip_message = f' Current server egress IP: {server_ip}.' if server_ip else ''
                return None, (
                    'SafeTrade rejected this request because the server IP is not trusted for your API key '
                    '(authz.apikey_untrusted_ip). Add this server IP to your SafeTrade API key allowlist and retry.'
                    f'{ip_message}'
                )
        return None, 'SafeTrade authentication failed. Please verify your API key, secret, and API key permissions.'

    if response.status_code >= 400:
        if isinstance(response_payload, dict):
            errors = response_payload.get('errors')
            if isinstance(errors, list) and errors:
                error_text = ', '.join(str(error) for error in errors)
                return None, f'SafeTrade returned HTTP {response.status_code}: {error_text}'
        return None, f'SafeTrade returned HTTP {response.status_code}. Please try again shortly.'

    try:
        payload = response.json()
    except ValueError:
        return None, 'SafeTrade returned an invalid JSON response.'

    member_info = payload.get('member') if isinstance(payload, dict) else None
    if member_info is None and isinstance(payload, dict):
        member_info = payload.get('data', payload)
    if not isinstance(member_info, dict):
        return None, 'SafeTrade response did not include member information.'

    return member_info, None


def _get_server_public_ip():
    """Best-effort lookup of the server's public egress IP for SafeTrade allowlisting."""
    endpoints = [
        ('https://api.ipify.org?format=json', 'json'),
        ('https://ifconfig.me/ip', 'text'),
    ]

    for url, response_type in endpoints:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                continue

            if response_type == 'json':
                payload = response.json()
                ip_value = payload.get('ip') if isinstance(payload, dict) else None
            else:
                ip_value = response.text.strip()

            if ip_value and isinstance(ip_value, str):
                return ip_value
        except (requests.RequestException, ValueError):
            continue

    return None


# Create your views here.
@login_required
def portfolio(request):
    """Display user's wallet portfolio"""
    # Get the user's wallet if it exists using the OneToOne relationship
    user_wallet = getattr(request.user, 'user_wallet', None)
    safe_trade_credentials = getattr(request.user, 'safe_trade_credentials', None)
    safe_trade_server_ip = _get_server_public_ip()
    
    # Create wallet on form submission
    if request.method == 'POST':
        action = request.POST.get('action', 'create_wallet')

        if action == 'save_safetrade':
            api_key = request.POST.get('safe_trade_api_key', '').strip()
            api_secret = request.POST.get('safe_trade_api_secret', '').strip()

            if not api_key:
                messages.error(request, 'SafeTrade API key is required.')
                return redirect('portfolio')

            if not api_secret and not safe_trade_credentials:
                messages.error(request, 'SafeTrade API secret is required for first-time setup.')
                return redirect('portfolio')

            if safe_trade_credentials:
                safe_trade_credentials.api_key = api_key
                if api_secret:
                    safe_trade_credentials.api_secret = api_secret
                safe_trade_credentials.save(update_fields=['api_key', 'api_secret', 'updated_at'])
            else:
                safe_trade_credentials = SafeTradeCredentials.objects.create(
                    user=request.user,
                    api_key=api_key,
                    api_secret=api_secret,
                )

            member_info, error = _fetch_safetrade_member_info(
                safe_trade_credentials.api_key,
                safe_trade_credentials.api_secret,
            )
            if error:
                messages.error(request, error)
            else:
                safe_trade_credentials.member_info = member_info
                safe_trade_credentials.last_synced_at = timezone.now()
                safe_trade_credentials.save(update_fields=['member_info', 'last_synced_at', 'updated_at'])
                messages.success(request, 'SafeTrade credentials saved and account info synced successfully.')

            return redirect('portfolio')

        if action == 'refresh_safetrade':
            if not safe_trade_credentials:
                messages.error(request, 'Save your SafeTrade API credentials first.')
                return redirect('portfolio')

            member_info, error = _fetch_safetrade_member_info(
                safe_trade_credentials.api_key,
                safe_trade_credentials.api_secret,
            )
            if error:
                messages.error(request, error)
            else:
                safe_trade_credentials.member_info = member_info
                safe_trade_credentials.last_synced_at = timezone.now()
                safe_trade_credentials.save(update_fields=['member_info', 'last_synced_at', 'updated_at'])
                messages.success(request, 'SafeTrade account info refreshed successfully.')
            return redirect('portfolio')

        # Create wallet if it doesn't exist
        if not user_wallet:
            # Get wallet name and passphrase from form
            wallet_name = request.POST.get('wallet_name', '').strip()
            passphrase = request.POST.get('passphrase', '').strip()
            
            # Validate wallet name
            if not wallet_name:
                messages.error(request, 'Wallet name is required.')
                return render(request, 'portfolio/wallet.html', {'user_wallet': user_wallet})
            
            # Validate wallet name length
            if len(wallet_name) > 100:
                messages.error(request, 'Wallet name must be 100 characters or less.')
                return render(request, 'portfolio/wallet.html', {'user_wallet': user_wallet})
            
            # Start by generating new entropy
            entropy = BIP39Entropy.generate(128)
            
            # Save the new wallet to the database
            user_wallet = UserWallet.objects.create(
                user=request.user,
                name=wallet_name,
                entropy=entropy,
                passphrase=passphrase
            )
            # Import the wallet into the RPC and store address details
            wallet_instance = Wallet(
                user_wallet.entropy,
                user_wallet.passphrase,
                network_mode=_active_network_mode(),
            )
            wallet = wallet_instance.get_wallet().from_derivation(
                BIP44Derivation(
                    cryptocurrencies.Evrmore.COIN_TYPE,
                    0,
                    CHANGES.EXTERNAL_CHAIN,
                    0,
                )
            )
            address = wallet.address()
            wif = wallet.wif()
            RPC.importprivkey(wif, str(user_wallet.entropy), False)
            WalletAddress.objects.get_or_create(
                wallet=user_wallet,
                network_mode=_active_network_mode(),
                account=0,
                index=0,
                is_change=False,
                defaults={
                    'address': address,
                    'wif': wif,
                },
            )
            messages.success(request, f'Wallet "{wallet_name}" created successfully!')
            return redirect('portfolio')
    
    context = {
        'user_wallet': user_wallet,
        'safe_trade_credentials': safe_trade_credentials,
        'safe_trade_member_info': safe_trade_credentials.member_info if safe_trade_credentials else None,
        'safe_trade_server_ip': safe_trade_server_ip,
    }
    return render(request, 'portfolio/wallet.html', context)

@login_required
def sync_balance(request):
    """Sync user's EVR balance from the blockchain"""
    user_wallet = getattr(request.user, 'user_wallet', None)
    
    if not user_wallet:
        messages.error(request, 'No wallet found to sync balance.')
        return redirect('portfolio')
    
    try:
        balance = _sync_user_evr_balance(user_wallet)
        if balance is not None:
            # Convert from base unit (satoshis) to display unit by multiplying by 1e-8
            display_balance = balance * Decimal('1e-8')
            messages.success(request, f'Balance synced successfully! Current balance: {display_balance:.8f} EVR')
        else:
            messages.error(request, 'Failed to sync balance. Please try again.')
    except Exception as e:
        messages.error(request, f'Error syncing balance: {str(e)}')
    
    return redirect('portfolio')

@login_required
def backup_wallet(request):
    """Allow user to backup their wallet mnemonic"""
    user_wallet = getattr(request.user, 'user_wallet', None)
    
    if not user_wallet:
        messages.error(request, 'No wallet found to backup.')
        return redirect('portfolio')
    
    # Generate mnemonic from stored entropy
    wallet_instance = Wallet(user_wallet.entropy, user_wallet.passphrase)
    mnemonic = wallet_instance.get_mnemonic()
    
    context = {
        'mnemonic': mnemonic,
    }
    return render(request, 'portfolio/backup.html', context)


@login_required
def wallet_transactions(request):
    """Display transaction history for the user's primary wallet address."""
    user_wallet = getattr(request.user, 'user_wallet', None)

    if not user_wallet:
        messages.error(request, 'No wallet found to view transactions.')
        return redirect('portfolio')

    wallet_addresses = _get_user_wallet_addresses(request.user, include_change=True)
    if not wallet_addresses:
        messages.error(request, 'Unable to determine your wallet addresses.')
        return redirect('portfolio')

    requested_limit = str(request.GET.get('limit', 'all') or 'all').strip().lower()
    if requested_limit in ('', 'all'):
        limit = None
    else:
        try:
            limit = max(1, min(250, int(requested_limit)))
        except (TypeError, ValueError):
            limit = None

    raw_txids = []
    total_indexed_transactions = 0
    has_more_transactions = False
    txids_error = None
    try:
        txid_response = RPC.getaddresstxids({'addresses': wallet_addresses})
        if not isinstance(txid_response, list):
            raise Exception(f'Unexpected transaction history response: {txid_response}')

        deduplicated_txids = OrderedDict()
        for txid in reversed(txid_response):
            normalized_txid = str(txid or '').strip()
            if not normalized_txid or normalized_txid in deduplicated_txids:
                continue
            deduplicated_txids[normalized_txid] = None
        total_indexed_transactions = len(deduplicated_txids)
        if limit is None:
            raw_txids = list(deduplicated_txids.keys())
        else:
            raw_txids = list(deduplicated_txids.keys())[:limit]
            has_more_transactions = total_indexed_transactions > len(raw_txids)
    except Exception as exc:
        txids_error = str(exc)

    tx_summaries, deltas_error = _build_transaction_summaries(wallet_addresses, raw_txids) if raw_txids else ({}, None)
    transactions, detail_errors = _build_wallet_transaction_rows(raw_txids, tx_summaries) if raw_txids else ([], [])

    context = {
        'user_wallet': user_wallet,
        'address': wallet_addresses[0],
        'address_count': len(wallet_addresses),
        'network_mode': _active_network_mode(),
        'limit': limit,
        'showing_all_transactions': limit is None,
        'limit_options': _build_transaction_limit_options(limit),
        'load_more_limit_options': _build_load_more_limit_options(limit),
        'transactions': transactions,
        'total_indexed_transactions': total_indexed_transactions,
        'has_more_transactions': has_more_transactions,
        'txids_error': txids_error,
        'deltas_error': deltas_error,
        'detail_errors': detail_errors,
    }
    return render(request, 'portfolio/transactions.html', context)

@login_required
def recieve_funds(request):
    """Display wallet address for receiving funds"""
    user_wallet = getattr(request.user, 'user_wallet', None)
    
    if not user_wallet:
        messages.error(request, 'No wallet found to receive funds.')
        return redirect('portfolio')
    
    # Get wallet address
    address = _get_user_primary_address(request.user)
    address_qr_data_uri = build_qr_data_uri(address)
    
    context = {
        'address': address,
        'address_qr_data_uri': address_qr_data_uri,
    }
    return render(request, 'portfolio/receive.html', context)

@login_required
def send_funds(request):
    """Handle sending funds from the user's wallet"""
    user_wallet = getattr(request.user, 'user_wallet', None)
    
    if not user_wallet:
        messages.error(request, 'No wallet found to send funds.')
        return redirect('portfolio')

    if request.method == 'POST':
        action = str(request.POST.get('action', 'send_funds') or 'send_funds').strip().lower()
        if action == 'create_profile':
            return _create_wallet_profile(request)
        if action == 'set_main_profile':
            return _set_main_wallet_profile(request)
    
    # Read-only fetch for send form rendering to avoid write contention.
    asset_balances, _ = _get_user_asset_balances(request.user, sync_tracking=False)
    evr_balance_sats = _sync_user_evr_balance(user_wallet)
    if evr_balance_sats is not None:
        evr_balance = evr_balance_sats * Decimal('1e-8')
    else:
        evr_balance = _get_stored_network_balance(user_wallet) * Decimal('1e-8')
    asset_options = []
    for symbol, amount in sorted(asset_balances.items()):
        if symbol == 'EVR':
            continue
        units = _get_asset_units(symbol)
        step = _step_string_for_units(units)
        asset_options.append({
            'symbol': symbol,
            'balance_display': _format_asset_amount(amount),
            'balance_value': str(amount),
            'units': units,
            'step': step,
            'min_value': step,
        })
    receive_address = _get_user_primary_address(request.user)
    receive_address_qr_data_uri = build_qr_data_uri(receive_address)
    main_profile = _get_or_create_main_wallet_profile(request.user)
    wallet_profiles = _get_wallet_profiles(request.user)

    if request.method == 'POST':
        currency = request.POST.get('currency', 'EVR').strip().upper()
        recipient_address = request.POST.get('recipient_address', '').strip()
        amount = request.POST.get('amount', '').strip()
        amount_units = 8 if currency == 'EVR' else _get_asset_units(currency)
        
        # Validate inputs
        if not recipient_address or not amount:
            messages.error(request, 'Recipient address and amount are required.')
            return redirect('send_funds')
        
        try:
            amount_decimal = _normalize_amount_for_units(amount, amount_units)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect('send_funds')

        if currency == 'EVR':
            if amount_decimal > evr_balance:
                messages.error(request, 'Amount exceeds your EVR balance.')
                return redirect('send_funds')
        else:
            asset_balance = asset_balances.get(currency)
            if asset_balance is None:
                messages.error(request, 'Selected asset not found in your wallet.')
                return redirect('send_funds')
            if amount_decimal > asset_balance:
                messages.error(request, 'Amount exceeds your asset balance.')
                return redirect('send_funds')
        
        from_address = _get_user_primary_address(request.user)
        if not from_address:
            messages.error(request, 'Unable to determine a source wallet address.')
            return redirect('send_funds')

        try:
            sender_wif = _derive_user_wif_for_address(request.user, from_address)
        except Exception as e:
            messages.error(request, f'Unable to derive sender signing key: {str(e)}')
            return redirect('send_funds')

        coin_change_address = from_address
        if currency != 'EVR':
            try:
                coin_change_address = _ensure_change_wallet_address(user_wallet).address
            except Exception as e:
                messages.error(request, f'Unable to determine a change wallet address: {str(e)}')
                return redirect('send_funds')

        # Create and send transaction via createrawtransaction
        try:
            if currency == 'EVR':
                tx_result = create_and_send_evr_transaction(
                    from_address=from_address,
                    to_address=recipient_address,
                    amount_evr=amount_decimal,
                    change_address=coin_change_address,
                    wif_keys=[sender_wif],
                )
            else:
                tx_result = create_and_send_asset_transfer_transaction(
                    from_address=from_address,
                    to_address=recipient_address,
                    asset_name=currency,
                    asset_quantity=amount_decimal,
                    change_address=coin_change_address,
                    asset_change_address=from_address,
                    wif_keys=[sender_wif],
                )

            txid = tx_result['txid']
            messages.success(request, f'Successfully sent {amount_decimal} to {recipient_address}. Transaction ID: {txid}')
        except Exception as e:
            messages.error(request, f'Error sending funds: {str(e)}')
        
        return redirect('send_funds')
    
    return render(request, 'portfolio/send.html', {
        'asset_options': asset_options,
        'evr_balance': evr_balance,
        'main_profile': main_profile,
        'wallet_profiles': wallet_profiles,
        'receive_address': receive_address,
        'receive_address_qr_data_uri': receive_address_qr_data_uri,
    })


@login_required
@require_http_methods(["GET"])
def validate_address(request):
    """Validate an Evrmore address via RPC."""
    address = request.GET.get('address', '').strip()
    if not address:
        return JsonResponse({'isvalid': False})

    try:
        result = RPC.validateaddress(address)
        if isinstance(result, dict) and 'isvalid' in result:
            return JsonResponse({'isvalid': bool(result['isvalid'])})
    except Exception:
        pass

    return JsonResponse({'isvalid': False})


@login_required
@require_http_methods(["GET"])
def address_qr(request):
    """Generate a QR image payload for a provided address-like string."""
    address = request.GET.get('address', '').strip()
    if not address:
        return JsonResponse({'ok': False, 'error': 'Address is required.'}, status=400)

    if len(address) > 256:
        return JsonResponse({'ok': False, 'error': 'Address exceeds maximum length.'}, status=400)

    qr_data_uri = build_qr_data_uri(address)
    if not qr_data_uri:
        return JsonResponse({'ok': False, 'error': 'Unable to generate QR code.'}, status=500)

    return JsonResponse({
        'ok': True,
        'address': address,
        'qr_data_uri': qr_data_uri,
    })
