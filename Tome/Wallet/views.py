from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from decimal import Decimal, InvalidOperation
from .models import UserWallet, WalletAddress
from .wallet import Wallet
from .rpc import RPC
from hdwallet.entropies import BIP39Entropy
from hdwallet.derivations import BIP44Derivation, CHANGES
from hdwallet import cryptocurrencies


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
        # Get wallet address
        wallet_instance = Wallet(user_wallet.entropy, user_wallet.passphrase)
        wallet = wallet_instance.get_wallet()
        address = wallet.address()
        
        # Call getaddressbalance RPC command
        balance_data = RPC.getaddressbalance(address)
        
        # Extract balance from response: {"balance": 0, "received": 0}
        if isinstance(balance_data, dict) and 'balance' in balance_data:
            balance = Decimal(str(balance_data['balance']))
            user_wallet.evr_liquidity = balance
            user_wallet.last_balance_update = timezone.now()
            user_wallet.save()
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
        is_change=False
    ).order_by('account', 'index').first()

    if address_record:
        return address_record.address

    # Fallback to deriving address from wallet entropy/passphrase
    try:
        wallet_instance = Wallet(user_wallet.entropy, user_wallet.passphrase)
        wallet = wallet_instance.get_wallet()
        return wallet.address()
    except Exception:
        return None


def _get_user_asset_balances(user):
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

    return asset_balances, None


def _format_asset_amount(amount):
    """Format Decimal amounts by trimming trailing zeros or flooring to int if whole."""
    amount_str = format(amount, 'f')
    if '.' in amount_str:
        amount_str = amount_str.rstrip('0').rstrip('.')
    return amount_str or '0'


# Create your views here.
@login_required
def portfolio(request):
    """Display user's wallet portfolio"""
    # Get the user's wallet if it exists using the OneToOne relationship
    user_wallet = getattr(request.user, 'user_wallet', None)
    
    # Create wallet on form submission
    if request.method == 'POST':
        # Create wallet if it doesn't exist
        if not user_wallet:
            # Get wallet name and passphrase from form
            wallet_name = request.POST.get('wallet_name', '').strip()
            passphrase = request.POST.get('passphrase', '').strip()
            
            # Validate wallet name
            if not wallet_name:
                messages.error(request, 'Wallet name is required.')
                return render(request, 'portfolio/index.html', {'user_wallet': user_wallet})
            
            # Validate wallet name length
            if len(wallet_name) > 100:
                messages.error(request, 'Wallet name must be 100 characters or less.')
                return render(request, 'portfolio/index.html', {'user_wallet': user_wallet})
            
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
            wallet_instance = Wallet(user_wallet.entropy, user_wallet.passphrase)
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
                address=address,
                wif=wif,
                account=0,
                index=0,
                is_change=False,
            )
            messages.success(request, f'Wallet "{wallet_name}" created successfully!')
            return redirect('portfolio')
    
    context = {
        'user_wallet': user_wallet,
    }
    return render(request, 'portfolio/index.html', context)

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
    wallet_instance = Wallet(user_wallet.entropy, user_wallet.passphrase)
    wallet = wallet_instance.get_wallet()
    address = wallet.address()
    
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
    
    asset_balances, _ = _get_user_asset_balances(request.user)
    evr_balance_sats = _sync_user_evr_balance(user_wallet)
    if evr_balance_sats is not None:
        evr_balance = evr_balance_sats * Decimal('1e-8')
    else:
        evr_balance = (user_wallet.evr_liquidity or Decimal('0')) * Decimal('1e-8')
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
        
        # Get wallet instance
        wallet_instance = Wallet(user_wallet.entropy, user_wallet.passphrase)
        wallet = wallet_instance.get_wallet()
        
        # Create and send transaction via RPC
        try:
            txid = RPC.sendtoaddress(recipient_address, float(amount_decimal), wallet)
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
