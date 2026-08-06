from .models import UserProfile
from Tome.rpc_client import (
    clear_active_network_mode,
    clear_active_rpc_endpoint_mode,
    set_active_network_mode,
    set_active_rpc_endpoint_mode,
)


class UserNetworkModeMiddleware:
    """Attach per-request Evrmore network mode to thread-local RPC routing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        selected_mode = 'testnet'
        selected_rpc_endpoint_mode = 'public'

        try:
            if request.user.is_authenticated:
                user_profile = getattr(request.user, 'profile', None)
                if user_profile is None:
                    user_profile, _created = UserProfile.objects.get_or_create(user=request.user)
                selected_mode = user_profile.network_mode
                selected_rpc_endpoint_mode = user_profile.rpc_endpoint_mode
        except Exception:
            # Keep request handling resilient; RPC routing will fall back to testnet.
            selected_mode = 'testnet'
            selected_rpc_endpoint_mode = 'public'

        set_active_network_mode(selected_mode)
        set_active_rpc_endpoint_mode(selected_rpc_endpoint_mode)
        try:
            response = self.get_response(request)
        finally:
            clear_active_network_mode()
            clear_active_rpc_endpoint_mode()

        return response
