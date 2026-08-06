from .models import UserProfile


def theme_context(request):
    """Add user's theme preference to all template contexts"""
    if request.user.is_authenticated:
        # Use get_or_create to safely handle concurrent requests
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        network_mode = user_profile.network_mode
        rpc_endpoint_mode = user_profile.rpc_endpoint_mode
        return {
            'user_theme': user_profile.theme,
            'user_network_mode': network_mode,
            'user_rpc_endpoint_mode': rpc_endpoint_mode,
            'user_network_display': 'Mainnet' if network_mode == 'mainnet' else 'Testnet',
            'user_rpc_endpoint_display': 'Local' if rpc_endpoint_mode == 'local' else 'Public',
        }
    return {
        'user_theme': 'default',
        'user_network_mode': 'testnet',
        'user_rpc_endpoint_mode': 'public',
        'user_network_display': 'Testnet',
        'user_rpc_endpoint_display': 'Public',
    }
