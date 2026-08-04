from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.utils import timezone

from .evrmore_auth import normalize_evrmore_address, verify_evrmore_signature
from .models import EvrmoreAuthenticationAddress


class EvrmoreWalletBackend(BaseBackend):
    def authenticate(self, request, evrmore_address=None, challenge=None, signature=None, **kwargs):
        if not evrmore_address or not challenge or not signature:
            return None

        normalized_address = normalize_evrmore_address(evrmore_address)
        if normalized_address is None:
            return None

        linked_address = (
            EvrmoreAuthenticationAddress.objects.select_related('user')
            .filter(address=normalized_address, user__is_active=True)
            .first()
        )
        if linked_address is None:
            return None

        if not verify_evrmore_signature(
            normalized_address,
            challenge,
            signature,
            request=request,
        ):
            return None

        linked_address.last_authenticated_at = timezone.now()
        linked_address.save(update_fields=['last_authenticated_at'])
        return linked_address.user

    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            return user_model.objects.get(pk=user_id, is_active=True)
        except user_model.DoesNotExist:
            return None