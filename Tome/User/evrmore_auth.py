import logging
import os

from base58 import b58decode_check
from django.conf import settings
from evrmore_authentication import EvrmoreAuth, verify_message
from evrmore_authentication.exceptions import AuthenticationError


logger = logging.getLogger(__name__)

EVRMORE_P2PKH_VERSION = 0x21
MAX_ADDRESS_LENGTH = 128
MAX_CHALLENGE_LENGTH = 512
MAX_SIGNATURE_LENGTH = 512


class EvrmoreAuthenticationUnavailable(Exception):
    pass


def normalize_evrmore_address(value):
    if not isinstance(value, str):
        return None

    address = value.strip()
    if not address or len(address) > MAX_ADDRESS_LENGTH:
        return None

    try:
        decoded_address = b58decode_check(address)
    except (TypeError, ValueError):
        return None

    if len(decoded_address) != 21 or decoded_address[0] != EVRMORE_P2PKH_VERSION:
        return None

    return address


def create_evrmore_challenge(address):
    normalized_address = normalize_evrmore_address(address)
    if normalized_address is None:
        raise ValueError('A valid Evrmore P2PKH address is required.')

    try:
        return _get_authentication_client().generate_challenge(
            normalized_address,
            expire_minutes=settings.EVRMORE_AUTH_CHALLENGE_EXPIRY_MINUTES,
        )
    except Exception as exc:
        logger.exception('Unable to generate an Evrmore authentication challenge.')
        raise EvrmoreAuthenticationUnavailable from exc


def verify_evrmore_signature(address, challenge, signature, request=None):
    normalized_address = normalize_evrmore_address(address)
    if normalized_address is None:
        return False

    if not isinstance(challenge, str) or not challenge.strip() or len(challenge) > MAX_CHALLENGE_LENGTH:
        return False

    if not isinstance(signature, str) or not signature.strip() or len(signature) > MAX_SIGNATURE_LENGTH:
        return False

    try:
        normalized_challenge = challenge.strip()
        normalized_signature = signature.strip()
        if not verify_message(normalized_address, normalized_signature, normalized_challenge):
            return False

        authentication_client = _get_authentication_client()
        session = authentication_client.authenticate(
            evrmore_address=normalized_address,
            challenge=normalized_challenge,
            signature=normalized_signature,
            ip_address=_client_ip_address(request),
            user_agent=_user_agent(request),
        )
        authentication_client.invalidate_token(session.token)
        return True
    except AuthenticationError:
        return False
    except Exception:
        logger.exception('Unable to verify an Evrmore authentication signature.')
        return False


def _get_authentication_client():
    os.environ['SQLITE_DB_PATH'] = str(settings.EVRMORE_AUTH_DATABASE_PATH)
    return EvrmoreAuth(jwt_secret=settings.EVRMORE_AUTH_JWT_SECRET)


def _client_ip_address(request):
    if request is None:
        return None

    return request.META.get('REMOTE_ADDR')


def _user_agent(request):
    if request is None:
        return None

    return request.META.get('HTTP_USER_AGENT', '')[:512]