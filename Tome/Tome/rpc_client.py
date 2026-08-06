"""Network-aware Evrmore RPC routing with local-first fallback.

This module exposes a drop-in RPC client object that resolves the active
network per request and attempts RPC calls in this order:
1) local full node
2) public endpoint for the selected network
"""

import logging
import threading

from django.conf import settings as django_settings
from evrmore_rpc import EvrmoreClient
import requests


logger = logging.getLogger(__name__)

NETWORK_MAINNET = 'mainnet'
NETWORK_TESTNET = 'testnet'
RPC_ENDPOINT_PUBLIC = 'public'
RPC_ENDPOINT_LOCAL = 'local'
_thread_local = threading.local()


def normalize_network_mode(network_mode):
    normalized = str(network_mode or '').strip().lower()
    if normalized == NETWORK_MAINNET:
        return NETWORK_MAINNET
    return NETWORK_TESTNET


def set_active_network_mode(network_mode):
    _thread_local.network_mode = normalize_network_mode(network_mode)


def get_active_network_mode():
    configured_default = getattr(django_settings, 'DEFAULT_EVRMORE_NETWORK', NETWORK_TESTNET)
    fallback_default = normalize_network_mode(configured_default)
    return normalize_network_mode(getattr(_thread_local, 'network_mode', fallback_default))


def clear_active_network_mode():
    if hasattr(_thread_local, 'network_mode'):
        delattr(_thread_local, 'network_mode')


def normalize_rpc_endpoint_mode(rpc_endpoint_mode):
    normalized = str(rpc_endpoint_mode or '').strip().lower()
    if normalized == RPC_ENDPOINT_LOCAL:
        return RPC_ENDPOINT_LOCAL
    return RPC_ENDPOINT_PUBLIC


def set_active_rpc_endpoint_mode(rpc_endpoint_mode):
    _thread_local.rpc_endpoint_mode = normalize_rpc_endpoint_mode(rpc_endpoint_mode)


def get_active_rpc_endpoint_mode():
    configured_default = getattr(django_settings, 'DEFAULT_EVRMORE_RPC_ENDPOINT_MODE', RPC_ENDPOINT_PUBLIC)
    fallback_default = normalize_rpc_endpoint_mode(configured_default)
    return normalize_rpc_endpoint_mode(getattr(_thread_local, 'rpc_endpoint_mode', fallback_default))


def clear_active_rpc_endpoint_mode():
    if hasattr(_thread_local, 'rpc_endpoint_mode'):
        delattr(_thread_local, 'rpc_endpoint_mode')


class RoutedEvrmoreClient:
    """Proxy client that retries Evrmore RPC calls across configured backends."""

    def __init__(self):
        self._clients = {}

    def __getattr__(self, method_name):
        def _wrapped(*args, **kwargs):
            return self._call_with_fallback(method_name, *args, **kwargs)

        return _wrapped

    def _call_with_fallback(self, method_name, *args, **kwargs):
        network_mode = get_active_network_mode()
        rpc_endpoint_mode = get_active_rpc_endpoint_mode()
        attempt_errors = []

        for backend_name, client in self._get_backends(network_mode, rpc_endpoint_mode):
            method = getattr(client, method_name, None)
            if method is None:
                attempt_errors.append(f'{backend_name}: method unavailable')
                continue

            try:
                return method(*args, **kwargs)
            except Exception as exc:
                error_message = f'{backend_name}: {str(exc)}'
                attempt_errors.append(error_message)
                logger.warning(
                    'RPC call failed. network=%s endpoint_mode=%s backend=%s method=%s error=%s',
                    network_mode,
                    rpc_endpoint_mode,
                    backend_name,
                    method_name,
                    str(exc),
                )

        combined_errors = ' | '.join(attempt_errors) if attempt_errors else 'No backends available'
        raise Exception(
            f"RPC call '{method_name}' failed for network '{network_mode}' "
            f"with endpoint mode '{rpc_endpoint_mode}'. "
            f'Attempts: {combined_errors}'
        )

    def _get_backends(self, network_mode, rpc_endpoint_mode):
        local_backend = ('local', self._get_local_client(network_mode))
        public_backend = ('public', self._get_public_client(network_mode))
        if rpc_endpoint_mode == RPC_ENDPOINT_LOCAL:
            return [local_backend, public_backend]
        return [public_backend, local_backend]

    def _get_local_client(self, network_mode):
        cache_key = ('local', network_mode)
        if cache_key in self._clients:
            return self._clients[cache_key]

        timeout = getattr(django_settings, 'RPC_TIMEOUT_SECONDS', 10)
        default_datadir = getattr(django_settings, 'RPC_DATADIR', '/tmp/evrmore')

        if network_mode == NETWORK_MAINNET:
            datadir = getattr(django_settings, 'RPC_MAINNET_DATADIR', default_datadir)
            testnet = False
            rpcuser = getattr(django_settings, 'RPC_MAINNET_USER', None)
            rpcpassword = getattr(django_settings, 'RPC_MAINNET_PASSWORD', None)
            rpcport = getattr(django_settings, 'RPC_MAINNET_PORT', None)
        else:
            datadir = getattr(django_settings, 'RPC_TESTNET_DATADIR', default_datadir)
            testnet = True
            rpcuser = getattr(django_settings, 'RPC_TESTNET_USER', None)
            rpcpassword = getattr(django_settings, 'RPC_TESTNET_PASSWORD', None)
            rpcport = getattr(django_settings, 'RPC_TESTNET_PORT', None)

        kwargs = {
            'datadir': datadir,
            'testnet': testnet,
            'timeout': timeout,
        }

        if rpcuser:
            kwargs['rpcuser'] = rpcuser
        if rpcpassword:
            kwargs['rpcpassword'] = rpcpassword
        if rpcport is not None:
            kwargs['rpcport'] = int(rpcport)

        client = EvrmoreClient(**kwargs)
        self._clients[cache_key] = client
        return client

    def _get_public_client(self, network_mode):
        cache_key = ('public', network_mode)
        if cache_key in self._clients:
            return self._clients[cache_key]

        timeout = getattr(django_settings, 'RPC_PUBLIC_TIMEOUT_SECONDS', 10)
        if network_mode == NETWORK_MAINNET:
            url = getattr(
                django_settings,
                'EVRMORE_PUBLIC_RPC_MAINNET_URL',
                'https://evr-rpc-mainnet.evrmorecoin.org/rpc',
            )
        else:
            url = getattr(
                django_settings,
                'EVRMORE_PUBLIC_RPC_TESTNET_URL',
                'https://evr-rpc-testnet.evrmorecoin.org/rpc',
            )

        client = PublicRpcClient(url=url, timeout=timeout)
        self._clients[cache_key] = client
        return client


class PublicRpcClient:
    """Minimal JSON-RPC client for HTTPS public endpoints."""

    def __init__(self, url, timeout=10):
        self.url = str(url).rstrip('/')
        self.timeout = timeout

    def __getattr__(self, method_name):
        def _call(*args, **kwargs):
            params = list(args)
            if kwargs:
                params.append(kwargs)

            payload = {
                'jsonrpc': '1.0',
                'id': 'defitome-public-rpc',
                'method': method_name,
                'params': params,
            }

            response = requests.post(
                self.url,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()

            body = response.json()
            if body.get('error'):
                raise Exception(str(body['error']))
            return body.get('result')

        return _call


RPC = RoutedEvrmoreClient()


def get_current_network_mode():
    return get_active_network_mode()


def get_current_rpc_endpoint_mode():
    return get_active_rpc_endpoint_mode()
