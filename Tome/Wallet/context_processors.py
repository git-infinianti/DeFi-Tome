from .views import _sync_user_evr_balance
from decimal import Decimal


def wallet_balance(request):
    """
    Context processor that adds wallet balance to all templates.
    Automatically syncs balance from blockchain on every page load.
    """
    if request.user.is_authenticated:
        user_wallet = getattr(request.user, 'user_wallet', None)
        if user_wallet:
            # Sync balance from blockchain
            balance = _sync_user_evr_balance(user_wallet)
            # Convert from base unit (satoshis) to display unit by multiplying by 1e-8
            display_balance = balance * Decimal('1e-8') if balance is not None else user_wallet.evr_liquidity * Decimal('1e-8')
            return {
                'user_wallet_balance': display_balance,
                'has_wallet': True
            }
    
    return {
        'user_wallet_balance': None,
        'has_wallet': False
    }
