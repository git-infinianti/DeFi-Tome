from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.db import OperationalError
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import time
import requests
from .models import UserWallet, WalletAddress, SafeTradeCredentials
from .wallet import Wallet
from .asset_tracking import sync_tracked_assets
from .rpc import RPC, create_and_send_evr_transaction, create_and_send_asset_transfer_transaction
from hdwallet.entropies import BIP39Entropy
from hdwallet.derivations import BIP44Derivation, CHANGES
from hdwallet import cryptocurrencies
from Tome.rpc_client import get_current_network_mode


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

    address_record = WalletAddress.objects.filter(
        wallet=user_wallet,
        network_mode=_active_network_mode(),
        is_change=False
    ).order_by('account', 'index').first()

    if address_record:
        return address_record.address

    # Fallback to deriving address from wallet entropy/passphrase
    try:
        wallet_instance = _wallet_for_network(user_wallet)
        wallet = wallet_instance.get_wallet()
        address = wallet.address()
        wif = wallet.wif()

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
        return address
    except Exception:
        return None


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
def recieve_funds(request):
    """Display wallet address for receiving funds"""
    user_wallet = getattr(request.user, 'user_wallet', None)
    
    if not user_wallet:
        messages.error(request, 'No wallet found to receive funds.')
        return redirect('portfolio')
    
    # Get wallet address
    address = _get_user_primary_address(request.user)
    
    context = {
        'address': address,
    }
    return render(request, 'portfolio/receive.html', context)

@login_required
def send_funds(request):
    """Handle sending funds from the user's wallet"""
    user_wallet = getattr(request.user, 'user_wallet', None)
    
    if not user_wallet:
        messages.error(request, 'No wallet found to send funds.')
        return redirect('portfolio')
    
    # Read-only fetch for send form rendering to avoid write contention.
    asset_balances, _ = _get_user_asset_balances(request.user, sync_tracking=False)
    evr_balance_sats = _sync_user_evr_balance(user_wallet)
    if evr_balance_sats is not None:
        evr_balance = evr_balance_sats * Decimal('1e-8')
    else:
        evr_balance = _get_stored_network_balance(user_wallet) * Decimal('1e-8')
    asset_options = [
        {
            'symbol': symbol,
            'balance_display': _format_asset_amount(amount),
            'balance_value': str(amount)
        }
        for symbol, amount in sorted(asset_balances.items())
        if symbol != 'EVR'
    ]

    if request.method == 'POST':
        currency = request.POST.get('currency', 'EVR').strip().upper()
        recipient_address = request.POST.get('recipient_address', '').strip()
        amount = request.POST.get('amount', '').strip()
        
        # Validate inputs
        if not recipient_address or not amount:
            messages.error(request, 'Recipient address and amount are required.')
            return redirect('send_funds')
        
        try:
            amount_decimal = Decimal(str(amount))
            if amount_decimal <= 0:
                raise ValueError
        except (ValueError, InvalidOperation):
            messages.error(request, 'Invalid amount specified.')
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

        # Create and send transaction via createrawtransaction
        try:
            if currency == 'EVR':
                tx_result = create_and_send_evr_transaction(
                    from_address=from_address,
                    to_address=recipient_address,
                    amount_evr=amount_decimal,
                    change_address=from_address,
                    wif_keys=[sender_wif],
                )
            else:
                tx_result = create_and_send_asset_transfer_transaction(
                    from_address=from_address,
                    to_address=recipient_address,
                    asset_name=currency,
                    asset_quantity=amount_decimal,
                    change_address=from_address,
                    wif_keys=[sender_wif],
                )

            txid = tx_result['txid']
            messages.success(request, f'Successfully sent {amount_decimal} to {recipient_address}. Transaction ID: {txid}')
        except Exception as e:
            messages.error(request, f'Error sending funds: {str(e)}')
        
        return redirect('send_funds')
    
    return render(request, 'portfolio/send.html', {
        'asset_options': asset_options,
        'evr_balance': evr_balance
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
