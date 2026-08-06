from .views import _get_stored_network_balance
from decimal import Decimal


def wallet_balance(request):
    """
    Context processor that adds wallet balance to all templates.
    Automatically syncs balance from blockchain on every page load.
    """
    if request.user.is_authenticated:
        user_wallet = getattr(request.user, 'user_wallet', None)
        if user_wallet:
            # Read from stored network-specific balance to keep rendering side-effect free.
            display_balance = _get_stored_network_balance(user_wallet) * Decimal('1e-8')
            return {
                'user_wallet_balance': display_balance,
                'has_wallet': True
            }
    
    return {
        'user_wallet_balance': None,
        'has_wallet': False
    }
