from collections import OrderedDict
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP
from Tome.rpc_client import RPC

SATOSHIS_PER_EVR = Decimal('100000000')
DEFAULT_FEE_EVR = Decimal('0.0001')
DEFAULT_FEE_CONF_TARGET = 6
DEFAULT_FEE_ESTIMATE_MODE = 'CONSERVATIVE'
FEE_SAFETY_MULTIPLIER = Decimal('1.05')
DUST_THRESHOLD_SATS = 546
MAX_SEQUENCE = 0xFFFFFFFF
RBF_SEQUENCE = 0xFFFFFFFD
LOCKTIME_SEQUENCE = 0xFFFFFFFE

BURN_ADDRESS_ISSUE_ASSET = 'EXissueAssetXXXXXXXXXXXXXXXXYiYRBD'
BURN_ADDRESS_ISSUE_SUBASSET = 'EXissueSubAssetXXXXXXXXXXXXXWW1ASo'
BURN_ADDRESS_ISSUE_UNIQUE = 'EXissueUniqueAssetXXXXXXXXXXTZjZJ5'
BURN_ADDRESS_REISSUE_ASSET = 'EXReissueAssetXXXXXXXXXXXXXXY1ANQH'
BURN_ADDRESS_ISSUE_RESTRICTED = 'EXissueRestrictedXXXXXXXXXXXZZMynb'
BURN_ADDRESS_ISSUE_QUALIFIER = 'EXissueQuaLifierXXXXXXXXXXXXW5Zxyf'
BURN_ADDRESS_ISSUE_SUBQUALIFIER = 'EXissueSubQuaLifierXXXXXXXXXUgTjtu'
BURN_ADDRESS_TAG = 'EXaddTagBurnXXXXXXXXXXXXXXXXb5HLXh'

# Create inputs and outputs for a raw transaction
def itxo(txid, vout):
    return {"txid": txid, "vout": vout}

def utxo(address, amount):
    return {address: amount}


def _to_decimal_evr(amount):
    return Decimal(str(amount)).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)


def _to_satoshis(amount):
    return int(_to_decimal_evr(amount) * SATOSHIS_PER_EVR)


def _satoshis_to_evr(satoshis):
    return (Decimal(satoshis) / SATOSHIS_PER_EVR).quantize(Decimal('0.00000001'), rounding=ROUND_DOWN)


def _evr_output_value(amount):
    return format(_to_decimal_evr(amount), 'f')


def _estimate_tx_size_bytes(input_count, output_count):
    # Approximation for non-segwit style transaction weight in bytes.
    return 10 + (int(input_count) * 148) + (int(output_count) * 34)


def _raw_tx_size_bytes(raw_tx_hex):
    try:
        normalized = str(raw_tx_hex or '').strip()
    except Exception:
        return 0

    if not normalized or len(normalized) % 2 != 0:
        return 0

    return len(normalized) // 2


def _estimate_signed_tx_size_bytes(raw_tx_hex, input_count):
    unsigned_size = _raw_tx_size_bytes(raw_tx_hex)
    if unsigned_size <= 0:
        return 0

    # P2PKH-style inputs are ~41 bytes unsigned and ~148 bytes signed.
    per_input_signature_overhead = 107
    return unsigned_size + (int(input_count) * per_input_signature_overhead)


def _get_estimated_feerate_evr_per_kb(conf_target=DEFAULT_FEE_CONF_TARGET,
                                      estimate_mode=DEFAULT_FEE_ESTIMATE_MODE):
    target = max(1, min(1008, int(conf_target or DEFAULT_FEE_CONF_TARGET)))
    mode = str(estimate_mode or DEFAULT_FEE_ESTIMATE_MODE).upper()

    call_errors = []
    result = None

    for call in (
        lambda: RPC.estimatesmartfee(target, mode),
        lambda: RPC.estimatesmartfee(target),
    ):
        try:
            result = call()
            break
        except Exception as exc:
            call_errors.append(str(exc))

    if result is None:
        return None, {'errors': call_errors}

    if not isinstance(result, dict):
        return None, {'errors': [f'Unexpected estimatesmartfee response: {result}']}

    feerate = result.get('feerate')
    if feerate is None:
        return None, {'errors': result.get('errors') or ['Fee estimate missing feerate.'], 'blocks': result.get('blocks')}

    try:
        feerate_decimal = Decimal(str(feerate))
    except Exception:
        return None, {'errors': [f'Invalid feerate returned: {feerate}'], 'blocks': result.get('blocks')}

    if feerate_decimal <= 0:
        return None, {'errors': [f'Non-positive feerate returned: {feerate_decimal}'], 'blocks': result.get('blocks')}

    return feerate_decimal, {'blocks': result.get('blocks')}


def _parse_positive_decimal(value):
    try:
        parsed = Decimal(str(value))
    except Exception:
        return None

    if parsed <= 0:
        return None
    return parsed


def _get_fee_floor_evr_per_kb():
    """Return a conservative fee-rate floor from relay and mempool settings."""
    candidates = []
    errors = []

    try:
        mempool_info = RPC.getmempoolinfo()
        if isinstance(mempool_info, dict):
            mempool_floor = _parse_positive_decimal(mempool_info.get('mempoolminfee'))
            if mempool_floor is not None:
                candidates.append(mempool_floor)
    except Exception as exc:
        errors.append(f'getmempoolinfo: {str(exc)}')

    try:
        network_info = RPC.getnetworkinfo()
        if isinstance(network_info, dict):
            relay_fee = _parse_positive_decimal(network_info.get('relayfee'))
            incremental_fee = _parse_positive_decimal(network_info.get('incrementalfee'))
            if relay_fee is not None:
                candidates.append(relay_fee)
            if incremental_fee is not None:
                candidates.append(incremental_fee)
    except Exception as exc:
        errors.append(f'getnetworkinfo: {str(exc)}')

    if not candidates:
        return None, {'errors': errors}

    return max(candidates), {'errors': errors}


def _resolve_fee_satoshis(explicit_fee_evr, input_count, output_count,
                          conf_target=DEFAULT_FEE_CONF_TARGET,
                          estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
                          fallback_fee_evr=DEFAULT_FEE_EVR,
                          tx_size_bytes=None):
    if explicit_fee_evr is not None:
        return _to_satoshis(explicit_fee_evr)

    feerate, _meta = _get_estimated_feerate_evr_per_kb(
        conf_target=conf_target,
        estimate_mode=estimate_mode,
    )
    fee_floor, _floor_meta = _get_fee_floor_evr_per_kb()

    effective_feerate = None
    if feerate is not None and fee_floor is not None:
        effective_feerate = max(feerate, fee_floor)
    elif feerate is not None:
        effective_feerate = feerate
    elif fee_floor is not None:
        effective_feerate = fee_floor

    if effective_feerate is None:
        return _to_satoshis(fallback_fee_evr)

    estimated_size_bytes = int(tx_size_bytes or 0)
    if estimated_size_bytes <= 0:
        estimated_size_bytes = _estimate_tx_size_bytes(input_count, output_count)

    tx_size_kb = Decimal(estimated_size_bytes) / Decimal('1000')
    estimated_fee_evr = (effective_feerate * tx_size_kb * FEE_SAFETY_MULTIPLIER).quantize(
        Decimal('0.00000001'),
        rounding=ROUND_UP,
    )
    estimated_fee_satoshis = _to_satoshis(estimated_fee_evr)

    if estimated_fee_satoshis <= 0:
        return _to_satoshis(fallback_fee_evr)

    return estimated_fee_satoshis


def _sequence_for_input(locktime=0, replaceable=False):
    if replaceable:
        return RBF_SEQUENCE
    if locktime:
        return LOCKTIME_SEQUENCE
    return MAX_SEQUENCE


def _get_address_utxos(address, asset_name=None):
    last_error = None
    utxos = None

    request_obj = {'addresses': [address]}
    if asset_name:
        request_obj['assetName'] = str(asset_name)

    for call in (
        lambda: RPC.getaddressutxos(request_obj),
        lambda: RPC.getaddressutxos({**request_obj, 'chainInfo': True}),
        lambda: RPC.getaddressutxos(addresses=[address]),
        lambda: RPC.getaddressutxos(addresses=address),
    ):
        try:
            utxos = call()
            break
        except Exception as exc:
            last_error = exc

    if utxos is None and last_error is not None:
        raise Exception(f'Unable to fetch UTXOs for address {address}: {str(last_error)}')

    if not isinstance(utxos, list):
        raise Exception(f'Unexpected UTXO response for address {address}: {utxos}')
    return utxos


def _build_input_entry(utxo_item, sequence=None):
    txid = utxo_item.get('txid')
    vout = utxo_item.get('outputIndex', utxo_item.get('vout'))

    if txid is None or vout is None:
        raise Exception(f'Invalid UTXO entry: {utxo_item}')

    tx_input = {
        'txid': txid,
        'vout': int(vout),
    }

    if sequence is not None:
        tx_input['sequence'] = int(sequence)

    return tx_input


def _asset_name_from_utxo(utxo_item):
    return (
        utxo_item.get('assetName')
        or utxo_item.get('assetname')
        or utxo_item.get('asset')
    )


def _is_evr_utxo(utxo_item):
    asset_name = _asset_name_from_utxo(utxo_item)
    if not asset_name:
        return True
    return str(asset_name).upper() == 'EVR'


def _amount_from_utxo(utxo_item):
    explicit = (
        utxo_item.get('amount')
        or utxo_item.get('assetAmount')
        or utxo_item.get('assetamount')
    )
    if explicit is not None:
        return explicit

    satoshis = utxo_item.get('satoshis')
    if satoshis is None:
        return 0

    try:
        return Decimal(int(satoshis)) / Decimal('100000000')
    except (InvalidOperation, TypeError, ValueError):
        return 0


def _asset_amount_from_utxo(utxo_item):
    explicit = (
        utxo_item.get('assetAmount')
        or utxo_item.get('assetamount')
        or utxo_item.get('amount')
    )
    if explicit is not None:
        return explicit

    satoshis = utxo_item.get('satoshis')
    if satoshis is None:
        return 0

    try:
        return Decimal(int(satoshis)) / Decimal('100000000')
    except (InvalidOperation, TypeError, ValueError):
        return 0


def _find_authorization_input(utxos, authorization_asset_name, sequence=None):
    if not authorization_asset_name:
        return None

    auth_name = str(authorization_asset_name).upper()
    for utxo_item in utxos:
        utxo_asset = _asset_name_from_utxo(utxo_item)
        if not utxo_asset:
            continue

        if str(utxo_asset).upper() != auth_name:
            continue

        if Decimal(str(_amount_from_utxo(utxo_item))) <= 0:
            continue

        return _build_input_entry(utxo_item, sequence)

    raise Exception(f'Authorization asset input not found: {authorization_asset_name}')


def _owner_token_name(asset_name_or_root):
    asset_name = str(asset_name_or_root or '')
    if not asset_name:
        raise Exception('Asset name is required to derive owner token name.')

    if asset_name.endswith('!'):
        return asset_name

    if asset_name.startswith('$'):
        asset_name = asset_name[1:]

    root_name = asset_name.split('/')[0]
    root_name = root_name.split('#')[0]
    return f'{root_name}!'


def _is_subqualifier(asset_name):
    normalized = str(asset_name or '')
    return normalized.startswith('#') and '/' in normalized


def _root_qualifier_name(asset_name):
    normalized = str(asset_name or '')
    if not normalized.startswith('#'):
        raise Exception('Qualifier asset names must start with #.')
    return normalized.split('/')[0]


def _select_evr_inputs(address, required_satoshis, locktime=0, replaceable=False):
    utxos = sorted(_get_address_utxos(address), key=lambda item: int(item.get('satoshis', 0)), reverse=True)

    total_selected = 0
    selected_inputs = []
    sequence = _sequence_for_input(locktime=locktime, replaceable=replaceable)
    include_sequence = sequence != MAX_SEQUENCE

    for utxo_item in utxos:
        if not _is_evr_utxo(utxo_item):
            continue

        satoshis = int(utxo_item.get('satoshis', 0))
        if satoshis <= 0:
            continue

        selected_inputs.append(_build_input_entry(utxo_item, sequence if include_sequence else None))
        total_selected += satoshis

        if total_selected >= required_satoshis:
            break

    if total_selected < required_satoshis:
        needed = _satoshis_to_evr(required_satoshis)
        available = _satoshis_to_evr(total_selected)
        raise Exception(f'Insufficient EVR balance. Needed: {needed}, available: {available}.')

    return selected_inputs, total_selected


def _select_asset_inputs(address, asset_name, required_quantity, locktime=0, replaceable=False):
    required_quantity = Decimal(str(required_quantity))
    if required_quantity <= 0:
        raise Exception('Asset quantity must be greater than zero.')

    normalized_asset_name = str(asset_name).upper()
    sequence = _sequence_for_input(locktime=locktime, replaceable=replaceable)
    include_sequence = sequence != MAX_SEQUENCE
    selected_inputs = []
    selected_quantity = Decimal('0')
    selected_coin_satoshis = 0

    for utxo_item in _get_address_utxos(address, asset_name=normalized_asset_name):
        utxo_asset_name = _asset_name_from_utxo(utxo_item)
        if not utxo_asset_name or str(utxo_asset_name).upper() != normalized_asset_name:
            continue

        try:
            asset_amount = Decimal(str(_asset_amount_from_utxo(utxo_item)))
        except (InvalidOperation, TypeError, ValueError):
            continue

        if asset_amount <= 0:
            continue

        selected_inputs.append(_build_input_entry(utxo_item, sequence if include_sequence else None))
        selected_quantity += asset_amount

        # Asset UTXO satoshis encode asset quantity and are not EVR coin value.
        if _is_evr_utxo(utxo_item):
            selected_coin_satoshis += int(utxo_item.get('satoshis', 0))

        if selected_quantity >= required_quantity:
            break

    if selected_quantity < required_quantity:
        raise Exception(
            f'Insufficient {asset_name} balance. Needed: {required_quantity}, available: {selected_quantity}.'
        )

    return selected_inputs, selected_quantity, selected_coin_satoshis


def _select_inputs_for_operation(from_address, required_evr_satoshis,
                                 authorization_asset_name=None,
                                 locktime=0, replaceable=False):
    utxos = _get_address_utxos(from_address)
    sequence = _sequence_for_input(locktime=locktime, replaceable=replaceable)
    include_sequence = sequence != MAX_SEQUENCE

    selected_inputs = []
    selected_keys = set()
    selected_total_satoshis = 0

    if authorization_asset_name:
        auth_input = _find_authorization_input(
            utxos,
            authorization_asset_name=authorization_asset_name,
            sequence=sequence if include_sequence else None,
        )
        selected_inputs.append(auth_input)
        selected_keys.add((auth_input['txid'], auth_input['vout']))

        for utxo_item in utxos:
            txid = utxo_item.get('txid')
            vout = utxo_item.get('outputIndex', utxo_item.get('vout'))
            if txid == auth_input['txid'] and int(vout) == auth_input['vout']:
                selected_total_satoshis += int(utxo_item.get('satoshis', 0))
                break

    evr_candidates = sorted(utxos, key=lambda item: int(item.get('satoshis', 0)), reverse=True)

    for utxo_item in evr_candidates:
        txid = utxo_item.get('txid')
        vout = int(utxo_item.get('outputIndex', utxo_item.get('vout', -1)))
        satoshis = int(utxo_item.get('satoshis', 0))

        if txid is None or vout < 0 or satoshis <= 0:
            continue

        # Use only coin-like EVR UTXOs for fee/value funding.
        if not _is_evr_utxo(utxo_item):
            continue

        if (txid, vout) in selected_keys:
            continue

        selected_inputs.append(_build_input_entry(utxo_item, sequence if include_sequence else None))
        selected_keys.add((txid, vout))
        selected_total_satoshis += satoshis

        if selected_total_satoshis >= required_evr_satoshis:
            break

    if selected_total_satoshis < required_evr_satoshis:
        needed = _satoshis_to_evr(required_evr_satoshis)
        available = _satoshis_to_evr(selected_total_satoshis)
        raise Exception(f'Insufficient EVR balance for operation. Needed: {needed}, available: {available}.')

    return selected_inputs, selected_total_satoshis


def compose_asset_operation_outputs(coin_outputs, operation_address, operation_payload,
                                    owner_token_change_output=None):
    """
    Compose outputs for asset operations in required order:
    1) Coin outputs first (including burn output)
    2) Owner/root token change output next (if required)
    3) Asset operation output last
    """
    outputs = OrderedDict()

    for address, amount in coin_outputs.items():
        outputs[address] = _evr_output_value(amount)

    if owner_token_change_output:
        change_address, payload = owner_token_change_output
        outputs[change_address] = payload

    outputs[operation_address] = operation_payload
    return outputs


def _normalize_wifs(wif_keys):
    if wif_keys is None:
        return []
    if isinstance(wif_keys, (list, tuple, set)):
        return [str(item).strip() for item in wif_keys if str(item).strip()]
    wif = str(wif_keys).strip()
    return [wif] if wif else []


def sign_raw_transaction(raw_tx, wif_keys=None):
    normalized_wifs = _normalize_wifs(wif_keys)
    sign_errors = []
    signed = None

    if normalized_wifs:
        signer = getattr(RPC, 'signrawtransaction', None)
        if signer is None:
            sign_errors.append('signrawtransaction: RPC method unavailable.')
        else:
            for call in (
                lambda: signer(raw_tx, None, normalized_wifs, 'ALL'),
                lambda: signer(raw_tx, [], normalized_wifs, 'ALL'),
                lambda: signer(raw_tx, None, normalized_wifs),
                lambda: signer(raw_tx, [], normalized_wifs),
            ):
                try:
                    signed = call()
                    break
                except Exception as exc:
                    sign_errors.append(f'signrawtransaction(privkeys): {str(exc)}')

    if signed is None:
        for method_name in ('signrawtransactionwithwallet', 'signrawtransaction'):
            signer = getattr(RPC, method_name, None)
            if signer is None:
                continue

            try:
                signed = signer(raw_tx)
                break
            except Exception as exc:
                sign_errors.append(f'{method_name}: {str(exc)}')

    if signed is None:
        details = '; '.join(sign_errors) if sign_errors else 'No signing method available on RPC client.'
        raise Exception(f'Failed to sign raw transaction. {details}')

    if isinstance(signed, dict):
        if not signed.get('complete', True):
            errors = signed.get('errors', [])
            raise Exception(f'Raw transaction signing incomplete: {errors}')
        signed_hex = signed.get('hex')
    else:
        signed_hex = str(signed)

    if not signed_hex:
        raise Exception('RPC did not return signed transaction hex.')

    return signed_hex


def broadcast_signed_transaction(signed_hex):
    return RPC.sendrawtransaction(signed_hex)


def sign_and_broadcast_raw_transaction(raw_tx, wif_keys=None):
    signed_hex = sign_raw_transaction(raw_tx, wif_keys=wif_keys)
    return broadcast_signed_transaction(signed_hex)


def create_raw_asset_operation_transaction(
    from_address,
    operation_address,
    operation_payload,
    burn_amount_evr=Decimal('0'),
    burn_address=None,
    authorization_asset_name=None,
    owner_token_change_output=None,
    extra_coin_outputs=None,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    """
    Create a raw asset-operation transaction without signing or broadcasting it.
    """
    if not operation_address:
        raise Exception('operation_address is required.')

    burn_satoshis = _to_satoshis(burn_amount_evr)
    if burn_satoshis > 0 and not burn_address:
        raise Exception('burn_address is required when burn_amount_evr is greater than zero.')

    extra_outputs_count = len(extra_coin_outputs or {})
    owner_change_count = 1 if owner_token_change_output else 0
    asset_output_count = 1
    provisional_fee_sats = _resolve_fee_satoshis(
        explicit_fee_evr=fee_evr,
        input_count=1,
        output_count=1 + extra_outputs_count + owner_change_count + asset_output_count,
        conf_target=fee_conf_target,
        estimate_mode=fee_estimate_mode,
    )

    selected_inputs = []
    selected_total = 0
    final_fee_satoshis = provisional_fee_sats
    outputs = OrderedDict()
    raw_tx = None

    for _ in range(4):
        required_satoshis = burn_satoshis + final_fee_satoshis
        selected_inputs, selected_total = _select_inputs_for_operation(
            from_address=from_address,
            required_evr_satoshis=required_satoshis,
            authorization_asset_name=authorization_asset_name,
            locktime=locktime,
            replaceable=replaceable,
        )

        coin_outputs = OrderedDict()
        if burn_satoshis > 0:
            coin_outputs[burn_address] = _satoshis_to_evr(burn_satoshis)

        if extra_coin_outputs:
            for address, amount in extra_coin_outputs.items():
                coin_outputs[address] = _to_decimal_evr(amount)

        extra_coin_satoshis = sum(_to_satoshis(amount) for amount in coin_outputs.values())
        change_satoshis = selected_total - final_fee_satoshis - extra_coin_satoshis

        if change_satoshis < 0:
            needed = _satoshis_to_evr(final_fee_satoshis + extra_coin_satoshis)
            available = _satoshis_to_evr(selected_total)
            raise Exception(f'Insufficient EVR after output assembly. Needed: {needed}, available: {available}.')

        if change_satoshis >= DUST_THRESHOLD_SATS:
            coin_outputs[from_address] = _satoshis_to_evr(change_satoshis)

        outputs = compose_asset_operation_outputs(
            coin_outputs=coin_outputs,
            operation_address=operation_address,
            operation_payload=operation_payload,
            owner_token_change_output=owner_token_change_output,
        )

        raw_tx = create_raw_transaction(
            inputs=selected_inputs,
            outputs=outputs,
            locktime=locktime,
            replaceable=replaceable,
        )
        measured_signed_size = _estimate_signed_tx_size_bytes(raw_tx, len(selected_inputs))

        next_fee_satoshis = _resolve_fee_satoshis(
            explicit_fee_evr=fee_evr,
            input_count=len(selected_inputs),
            output_count=len(outputs),
            conf_target=fee_conf_target,
            estimate_mode=fee_estimate_mode,
            tx_size_bytes=measured_signed_size,
        )
        if next_fee_satoshis == final_fee_satoshis:
            break
        final_fee_satoshis = next_fee_satoshis

    if raw_tx is None:
        raw_tx = create_raw_transaction(
            inputs=selected_inputs,
            outputs=outputs,
            locktime=locktime,
            replaceable=replaceable,
        )

    return {
        'raw_tx': raw_tx,
        'inputs': selected_inputs,
        'outputs': dict(outputs),
    }


def create_and_send_asset_operation_transaction(
    from_address,
    operation_address,
    operation_payload,
    burn_amount_evr=Decimal('0'),
    burn_address=None,
    authorization_asset_name=None,
    owner_token_change_output=None,
    extra_coin_outputs=None,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
    wif_keys=None,
):
    """
    Create, sign, and broadcast an asset operation transaction.
    """
    tx_data = create_raw_asset_operation_transaction(
        from_address=from_address,
        operation_address=operation_address,
        operation_payload=operation_payload,
        burn_amount_evr=burn_amount_evr,
        burn_address=burn_address,
        authorization_asset_name=authorization_asset_name,
        owner_token_change_output=owner_token_change_output,
        extra_coin_outputs=extra_coin_outputs,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )
    txid = sign_and_broadcast_raw_transaction(tx_data['raw_tx'], wif_keys=wif_keys)

    return {
        'txid': txid,
        **tx_data,
    }


def create_raw_evr_transaction(from_address, to_address, amount_evr, change_address=None,
                               fee_evr=None, fee_conf_target=DEFAULT_FEE_CONF_TARGET,
                               fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE, locktime=0, replaceable=False,
                               extra_coin_outputs=None):
    """
    Create a raw EVR payment transaction without signing or broadcasting it.
    """
    amount_satoshis = _to_satoshis(amount_evr)
    if amount_satoshis <= 0:
        raise Exception('Amount must be greater than zero.')

    extra_outputs_count = len(extra_coin_outputs or {})
    provisional_fee_sats = _resolve_fee_satoshis(
        explicit_fee_evr=fee_evr,
        input_count=1,
        output_count=1 + extra_outputs_count + 1,
        conf_target=fee_conf_target,
        estimate_mode=fee_estimate_mode,
    )

    selected_inputs = []
    selected_total = 0
    outputs = OrderedDict()
    raw_tx = None
    final_fee_satoshis = provisional_fee_sats

    for _ in range(4):
        required_satoshis = amount_satoshis + final_fee_satoshis
        selected_inputs, selected_total = _select_evr_inputs(
            address=from_address,
            required_satoshis=required_satoshis,
            locktime=locktime,
            replaceable=replaceable,
        )

        outputs = OrderedDict()
        if extra_coin_outputs:
            for address, amount in extra_coin_outputs.items():
                outputs[address] = _evr_output_value(amount)

        outputs[to_address] = _evr_output_value(amount_evr)

        change_satoshis = selected_total - required_satoshis
        if change_satoshis >= DUST_THRESHOLD_SATS:
            outputs[change_address or from_address] = _evr_output_value(_satoshis_to_evr(change_satoshis))

        raw_tx = create_raw_transaction(
            inputs=selected_inputs,
            outputs=outputs,
            locktime=locktime,
            replaceable=replaceable,
        )
        measured_signed_size = _estimate_signed_tx_size_bytes(raw_tx, len(selected_inputs))

        next_fee_satoshis = _resolve_fee_satoshis(
            explicit_fee_evr=fee_evr,
            input_count=len(selected_inputs),
            output_count=len(outputs),
            conf_target=fee_conf_target,
            estimate_mode=fee_estimate_mode,
            tx_size_bytes=measured_signed_size,
        )
        if next_fee_satoshis == final_fee_satoshis:
            break
        final_fee_satoshis = next_fee_satoshis

    if raw_tx is None:
        raw_tx = create_raw_transaction(
            inputs=selected_inputs,
            outputs=outputs,
            locktime=locktime,
            replaceable=replaceable,
        )

    return {
        'raw_tx': raw_tx,
        'inputs': selected_inputs,
        'outputs': dict(outputs),
    }


def create_and_send_evr_transaction(from_address, to_address, amount_evr, change_address=None,
                                    fee_evr=None, fee_conf_target=DEFAULT_FEE_CONF_TARGET,
                                    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE, locktime=0, replaceable=False,
                                    extra_coin_outputs=None, wif_keys=None):
    """
    Create, sign, and broadcast an EVR payment transaction.
    """
    tx_data = create_raw_evr_transaction(
        from_address=from_address,
        to_address=to_address,
        amount_evr=amount_evr,
        change_address=change_address,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
        extra_coin_outputs=extra_coin_outputs,
    )
    txid = sign_and_broadcast_raw_transaction(tx_data['raw_tx'], wif_keys=wif_keys)

    return {
        'txid': txid,
        **tx_data,
    }


def create_raw_asset_transfer_transaction(from_address, to_address, asset_name, asset_quantity,
                                          change_address=None, fee_evr=None,
                                          fee_conf_target=DEFAULT_FEE_CONF_TARGET,
                                          fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
                                          locktime=0, replaceable=False,
                                          asset_change_address=None):
    """
    Create a raw asset transfer transaction without signing or broadcasting it.
    """
    try:
        asset_quantity_decimal = Decimal(str(asset_quantity))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise Exception('Asset quantity must be a valid decimal value.') from exc

    if asset_quantity_decimal <= 0:
        raise Exception('Asset quantity must be greater than zero.')

    sequence = _sequence_for_input(locktime=locktime, replaceable=replaceable)
    include_sequence = sequence != MAX_SEQUENCE

    # Select the asset-bearing inputs first, then add EVR inputs for fees.
    asset_inputs, selected_asset_quantity, _asset_input_coin_satoshis = _select_asset_inputs(
        address=from_address,
        asset_name=asset_name,
        required_quantity=asset_quantity_decimal,
        locktime=locktime,
        replaceable=replaceable,
    )

    selected_asset_change = selected_asset_quantity - asset_quantity_decimal

    utxos = _get_address_utxos(from_address)
    selected_keys = {(item['txid'], item['vout']) for item in asset_inputs}

    evr_candidates = sorted(
        [
            item for item in utxos
            if _is_evr_utxo(item)
            and int(item.get('satoshis', 0)) > 0
            and (
                item.get('txid'),
                int(item.get('outputIndex', item.get('vout', -1)))
            ) not in selected_keys
        ],
        key=lambda item: int(item.get('satoshis', 0)),
        reverse=True,
    )

    evr_inputs = []
    evr_total_satoshis = 0

    def _select_evr_fee_inputs(required_fee_sats):
        nonlocal evr_inputs, evr_total_satoshis
        evr_inputs = []
        evr_total_satoshis = 0
        for utxo_item in evr_candidates:
            satoshis = int(utxo_item.get('satoshis', 0))
            if satoshis <= 0:
                continue
            evr_inputs.append(_build_input_entry(utxo_item, sequence if include_sequence else None))
            evr_total_satoshis += satoshis
            if evr_total_satoshis >= required_fee_sats:
                break

        if evr_total_satoshis < required_fee_sats:
            needed = _satoshis_to_evr(required_fee_sats)
            available = _satoshis_to_evr(evr_total_satoshis)
            raise Exception(f'Insufficient EVR for fees. Needed: {needed}, available: {available}.')

    outputs = OrderedDict()
    coin_change_address = change_address or from_address
    asset_change_target = asset_change_address or from_address
    raw_tx = None

    # Iteratively re-estimate fee based on selected inputs/outputs.
    fee_satoshis = _resolve_fee_satoshis(
        explicit_fee_evr=fee_evr,
        input_count=len(asset_inputs) + 1,
        output_count=2 if selected_asset_change > 0 else 1,
        conf_target=fee_conf_target,
        estimate_mode=fee_estimate_mode,
    )

    for _ in range(4):
        _select_evr_fee_inputs(fee_satoshis)

        outputs = OrderedDict()
        outputs[to_address] = {
            'transfer': {
                asset_name: float(asset_quantity_decimal),
            }
        }

        if selected_asset_change > 0:
            if asset_change_target == to_address:
                raise Exception('Asset change address must differ from destination address.')
            outputs[asset_change_target] = {
                'transfer': {
                    asset_name: float(selected_asset_change),
                }
            }

        total_input_satoshis = evr_total_satoshis
        coin_change_satoshis = total_input_satoshis - fee_satoshis

        if coin_change_satoshis >= DUST_THRESHOLD_SATS:
            if coin_change_address in outputs:
                raise Exception(
                    'Coin change address conflicts with asset output address. '
                    'Use a distinct change_address or asset_change_address.'
                )
            outputs[coin_change_address] = _evr_output_value(_satoshis_to_evr(coin_change_satoshis))

        candidate_inputs = [*asset_inputs, *evr_inputs]
        raw_tx = create_raw_transaction(
            inputs=candidate_inputs,
            outputs=outputs,
            locktime=locktime,
            replaceable=replaceable,
        )
        measured_signed_size = _estimate_signed_tx_size_bytes(raw_tx, len(candidate_inputs))

        next_fee_sats = _resolve_fee_satoshis(
            explicit_fee_evr=fee_evr,
            input_count=len(candidate_inputs),
            output_count=len(outputs),
            conf_target=fee_conf_target,
            estimate_mode=fee_estimate_mode,
            tx_size_bytes=measured_signed_size,
        )
        if next_fee_sats == fee_satoshis:
            break
        fee_satoshis = next_fee_sats

    inputs = [*asset_inputs, *evr_inputs]
    if raw_tx is None:
        raw_tx = create_raw_transaction(
            inputs=inputs,
            outputs=outputs,
            locktime=locktime,
            replaceable=replaceable,
        )

    return {
        'raw_tx': raw_tx,
        'inputs': inputs,
        'outputs': dict(outputs),
    }


def create_and_send_asset_transfer_transaction(from_address, to_address, asset_name, asset_quantity,
                                               change_address=None, fee_evr=None,
                                               fee_conf_target=DEFAULT_FEE_CONF_TARGET,
                                               fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
                                               locktime=0, replaceable=False, wif_keys=None,
                                               asset_change_address=None):
    """
    Create, sign, and broadcast an asset transfer transaction.
    """
    tx_data = create_raw_asset_transfer_transaction(
        from_address=from_address,
        to_address=to_address,
        asset_name=asset_name,
        asset_quantity=asset_quantity,
        change_address=change_address,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
        asset_change_address=asset_change_address,
    )
    txid = sign_and_broadcast_raw_transaction(tx_data['raw_tx'], wif_keys=wif_keys)

    return {
        'txid': txid,
        **tx_data,
    }


def create_raw_atomic_asset_evr_swap_transaction(
    seller_address,
    buyer_address,
    asset_name,
    asset_quantity,
    payment_evr,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    """Create a single Evrmore transaction that exchanges an asset for EVR."""
    if not seller_address or not buyer_address:
        raise Exception('Seller and buyer addresses are required.')
    if seller_address == buyer_address:
        raise Exception('Seller and buyer addresses must be different.')
    if not asset_name:
        raise Exception('Asset name is required.')

    try:
        asset_quantity_decimal = Decimal(str(asset_quantity))
        payment_decimal = Decimal(str(payment_evr))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise Exception('Asset quantity and EVR payment must be valid decimal values.') from exc

    if asset_quantity_decimal <= 0 or payment_decimal <= 0:
        raise Exception('Asset quantity and EVR payment must be greater than zero.')

    seller_inputs, selected_asset_quantity, seller_input_satoshis = _select_asset_inputs(
        address=seller_address,
        asset_name=asset_name,
        required_quantity=asset_quantity_decimal,
        locktime=locktime,
        replaceable=replaceable,
    )
    asset_change_quantity = selected_asset_quantity - asset_quantity_decimal
    payment_satoshis = _to_satoshis(payment_decimal)
    provisional_fee_satoshis = _resolve_fee_satoshis(
        explicit_fee_evr=fee_evr,
        input_count=len(seller_inputs) + 1,
        output_count=4 if asset_change_quantity > 0 else 3,
        conf_target=fee_conf_target,
        estimate_mode=fee_estimate_mode,
    )

    final_fee_satoshis = provisional_fee_satoshis
    buyer_inputs = []
    buyer_input_satoshis = 0
    outputs = []
    raw_tx = None

    for _ in range(4):
        asset_output_count = 2 if asset_change_quantity > 0 else 1
        asset_output_satoshis = DUST_THRESHOLD_SATS * asset_output_count
        buyer_required_satoshis = (
            payment_satoshis
            + final_fee_satoshis
            + max(0, asset_output_satoshis - seller_input_satoshis)
        )
        buyer_inputs, buyer_input_satoshis = _select_evr_inputs(
            address=buyer_address,
            required_satoshis=buyer_required_satoshis,
            locktime=locktime,
            replaceable=replaceable,
        )

        seller_native_change = max(0, seller_input_satoshis - asset_output_satoshis)
        buyer_native_change = buyer_input_satoshis - buyer_required_satoshis

        outputs = [
            {
                buyer_address: {
                    'transfer': {
                        str(asset_name): float(asset_quantity_decimal),
                    }
                }
            },
        ]
        if asset_change_quantity > 0:
            outputs.append(
                {
                    seller_address: {
                        'transfer': {
                            str(asset_name): float(asset_change_quantity),
                        }
                    }
                }
            )

        seller_payout_satoshis = payment_satoshis + seller_native_change
        outputs.append({seller_address: _evr_output_value(_satoshis_to_evr(seller_payout_satoshis))})

        if buyer_native_change >= DUST_THRESHOLD_SATS:
            outputs.append({buyer_address: _evr_output_value(_satoshis_to_evr(buyer_native_change))})

        candidate_inputs = [*seller_inputs, *buyer_inputs]
        raw_tx = create_raw_transaction(
            inputs=candidate_inputs,
            outputs=outputs,
            locktime=locktime,
            replaceable=replaceable,
        )
        measured_signed_size = _estimate_signed_tx_size_bytes(raw_tx, len(candidate_inputs))

        next_fee_satoshis = _resolve_fee_satoshis(
            explicit_fee_evr=fee_evr,
            input_count=len(candidate_inputs),
            output_count=len(outputs),
            conf_target=fee_conf_target,
            estimate_mode=fee_estimate_mode,
            tx_size_bytes=measured_signed_size,
        )
        if next_fee_satoshis == final_fee_satoshis:
            break
        final_fee_satoshis = next_fee_satoshis

    if raw_tx is None:
        raw_tx = create_raw_transaction(
            inputs=[*seller_inputs, *buyer_inputs],
            outputs=outputs,
            locktime=locktime,
            replaceable=replaceable,
        )

    return {
        'raw_tx': raw_tx,
        'inputs': [*seller_inputs, *buyer_inputs],
        'outputs': outputs,
        'asset_change_quantity': asset_change_quantity,
        'fee_evr': _satoshis_to_evr(final_fee_satoshis),
    }


def create_and_send_atomic_asset_evr_swap_transaction(
    seller_address,
    buyer_address,
    asset_name,
    asset_quantity,
    payment_evr,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
    wif_keys=None,
):
    """Create, sign with both parties, and broadcast an atomic asset-for-EVR swap."""
    tx_data = create_raw_atomic_asset_evr_swap_transaction(
        seller_address=seller_address,
        buyer_address=buyer_address,
        asset_name=asset_name,
        asset_quantity=asset_quantity,
        payment_evr=payment_evr,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )
    txid = sign_and_broadcast_raw_transaction(tx_data['raw_tx'], wif_keys=wif_keys)

    return {
        'txid': txid,
        **tx_data,
    }


def create_and_send_transfer_with_message_transaction(
    from_address,
    to_address,
    asset_name,
    asset_quantity,
    message,
    expire_time,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    operation_payload = {
        'transferwithmessage': {
            asset_name: float(Decimal(str(asset_quantity))),
            'message': str(message),
            'expire_time': int(expire_time),
        }
    }

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=to_address,
        operation_payload=operation_payload,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )


def create_and_send_issue_asset_transaction(
    from_address,
    issuer_address,
    asset_name,
    asset_quantity,
    units,
    reissuable,
    has_ipfs,
    ipfs_hash='',
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
    wif_keys=None,
):
    is_subasset = '/' in str(asset_name)
    burn_address = BURN_ADDRESS_ISSUE_SUBASSET if is_subasset else BURN_ADDRESS_ISSUE_ASSET
    burn_amount = Decimal('100') if is_subasset else Decimal('500')

    operation_payload = {
        'issue': {
            'asset_name': str(asset_name),
            'asset_quantity': float(Decimal(str(asset_quantity))),
            'units': int(units),
            'reissuable': int(bool(reissuable)),
            'has_ipfs': int(bool(has_ipfs)),
        }
    }
    if has_ipfs:
        operation_payload['issue']['ipfs_hash'] = str(ipfs_hash)

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=issuer_address,
        operation_payload=operation_payload,
        burn_amount_evr=burn_amount,
        burn_address=burn_address,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
        wif_keys=wif_keys,
    )


def create_and_send_issue_unique_transaction(
    from_address,
    issuer_address,
    root_name,
    asset_tags,
    ipfs_hashes=None,
    owner_change_address=None,
    owner_change_quantity=1,
    burn_per_tag_evr=Decimal('5'),
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
    wif_keys=None,
):
    if not asset_tags:
        raise Exception('asset_tags must contain at least one unique tag.')

    operation_payload = {
        'issue_unique': {
            'root_name': str(root_name),
            'asset_tags': [str(tag) for tag in asset_tags],
        }
    }
    if ipfs_hashes:
        operation_payload['issue_unique']['ipfs_hashes'] = [str(item) for item in ipfs_hashes]

    owner_change_output = None
    if owner_change_address:
        owner_change_output = (
            owner_change_address,
            {
                'transfer': {
                    _owner_token_name(root_name): float(Decimal(str(owner_change_quantity))),
                }
            }
        )

    burn_total = Decimal(str(burn_per_tag_evr)) * Decimal(str(len(asset_tags)))

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=issuer_address,
        operation_payload=operation_payload,
        burn_amount_evr=burn_total,
        burn_address=BURN_ADDRESS_ISSUE_UNIQUE,
        authorization_asset_name=_owner_token_name(root_name),
        owner_token_change_output=owner_change_output,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
        wif_keys=wif_keys,
    )


def create_and_send_reissue_asset_transaction(
    from_address,
    issuer_address,
    asset_name,
    asset_quantity,
    reissuable=True,
    ipfs_hash='',
    owner_change_address=None,
    owner_change_quantity=1,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    operation_payload = {
        'reissue': {
            'asset_name': str(asset_name),
            'asset_quantity': float(Decimal(str(asset_quantity))),
            'reissuable': int(bool(reissuable)),
        }
    }
    if ipfs_hash:
        operation_payload['reissue']['ipfs_hash'] = str(ipfs_hash)
    if owner_change_address:
        operation_payload['reissue']['owner_change_address'] = str(owner_change_address)

    owner_change_output = None
    if owner_change_address:
        owner_change_output = (
            owner_change_address,
            {
                'transfer': {
                    _owner_token_name(asset_name): float(Decimal(str(owner_change_quantity))),
                }
            }
        )

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=issuer_address,
        operation_payload=operation_payload,
        burn_amount_evr=Decimal('100'),
        burn_address=BURN_ADDRESS_REISSUE_ASSET,
        authorization_asset_name=_owner_token_name(asset_name),
        owner_token_change_output=owner_change_output,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )


def create_and_send_issue_restricted_transaction(
    from_address,
    issuer_address,
    asset_name,
    asset_quantity,
    verifier_string,
    units,
    reissuable,
    has_ipfs,
    ipfs_hash='',
    owner_change_address=None,
    owner_change_quantity=1,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    operation_payload = {
        'issue_restricted': {
            'asset_name': str(asset_name),
            'asset_quantity': float(Decimal(str(asset_quantity))),
            'verifier_string': str(verifier_string),
            'units': int(units),
            'reissuable': int(bool(reissuable)),
            'has_ipfs': int(bool(has_ipfs)),
        }
    }
    if has_ipfs:
        operation_payload['issue_restricted']['ipfs_hash'] = str(ipfs_hash)
    if owner_change_address:
        operation_payload['issue_restricted']['owner_change_address'] = str(owner_change_address)

    owner_change_output = None
    if owner_change_address:
        owner_change_output = (
            owner_change_address,
            {
                'transfer': {
                    _owner_token_name(asset_name): float(Decimal(str(owner_change_quantity))),
                }
            }
        )

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=issuer_address,
        operation_payload=operation_payload,
        burn_amount_evr=Decimal('1500'),
        burn_address=BURN_ADDRESS_ISSUE_RESTRICTED,
        authorization_asset_name=_owner_token_name(asset_name),
        owner_token_change_output=owner_change_output,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )


def create_and_send_reissue_restricted_transaction(
    from_address,
    issuer_address,
    asset_name,
    asset_quantity,
    reissuable=True,
    verifier_string='',
    ipfs_hash='',
    owner_change_address=None,
    owner_change_quantity=1,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    operation_payload = {
        'reissue_restricted': {
            'asset_name': str(asset_name),
            'asset_quantity': float(Decimal(str(asset_quantity))),
            'reissuable': int(bool(reissuable)),
        }
    }
    if verifier_string:
        operation_payload['reissue_restricted']['verifier_string'] = str(verifier_string)
    if ipfs_hash:
        operation_payload['reissue_restricted']['ipfs_hash'] = str(ipfs_hash)
    if owner_change_address:
        operation_payload['reissue_restricted']['owner_change_address'] = str(owner_change_address)

    owner_change_output = None
    if owner_change_address:
        owner_change_output = (
            owner_change_address,
            {
                'transfer': {
                    _owner_token_name(asset_name): float(Decimal(str(owner_change_quantity))),
                }
            }
        )

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=issuer_address,
        operation_payload=operation_payload,
        burn_amount_evr=Decimal('100'),
        burn_address=BURN_ADDRESS_REISSUE_ASSET,
        authorization_asset_name=_owner_token_name(asset_name),
        owner_token_change_output=owner_change_output,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )


def create_and_send_issue_qualifier_transaction(
    from_address,
    issuer_address,
    asset_name,
    asset_quantity=1,
    has_ipfs=False,
    ipfs_hash='',
    root_change_address=None,
    change_quantity=1,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    operation_payload = {
        'issue_qualifier': {
            'asset_name': str(asset_name),
            'asset_quantity': float(Decimal(str(asset_quantity))),
            'has_ipfs': int(bool(has_ipfs)),
        }
    }
    if has_ipfs:
        operation_payload['issue_qualifier']['ipfs_hash'] = str(ipfs_hash)
    if root_change_address:
        operation_payload['issue_qualifier']['root_change_address'] = str(root_change_address)
    if change_quantity is not None:
        operation_payload['issue_qualifier']['change_quantity'] = float(Decimal(str(change_quantity)))

    is_sub = _is_subqualifier(asset_name)
    burn_amount = Decimal('100') if is_sub else Decimal('1000')
    burn_address = BURN_ADDRESS_ISSUE_SUBQUALIFIER if is_sub else BURN_ADDRESS_ISSUE_QUALIFIER
    auth_asset = _root_qualifier_name(asset_name) if is_sub else None

    owner_change_output = None
    if is_sub and root_change_address:
        owner_change_output = (
            root_change_address,
            {
                'transfer': {
                    _root_qualifier_name(asset_name): float(Decimal(str(change_quantity or 1))),
                }
            }
        )

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=issuer_address,
        operation_payload=operation_payload,
        burn_amount_evr=burn_amount,
        burn_address=burn_address,
        authorization_asset_name=auth_asset,
        owner_token_change_output=owner_change_output,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )


def create_and_send_tag_addresses_transaction(
    from_address,
    qualifier_change_address,
    qualifier,
    addresses,
    change_quantity=1,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    if not addresses:
        raise Exception('addresses must include at least one address.')

    operation_payload = {
        'tag_addresses': {
            'qualifier': str(qualifier),
            'addresses': [str(address) for address in addresses],
            'change_quantity': float(Decimal(str(change_quantity))),
        }
    }

    burn_amount = Decimal('0.1') * Decimal(str(len(addresses)))
    owner_change_output = (
        qualifier_change_address,
        {
            'transfer': {
                str(qualifier): float(Decimal(str(change_quantity))),
            }
        }
    )

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=qualifier_change_address,
        operation_payload=operation_payload,
        burn_amount_evr=burn_amount,
        burn_address=BURN_ADDRESS_TAG,
        authorization_asset_name=str(qualifier),
        owner_token_change_output=owner_change_output,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )


def create_and_send_untag_addresses_transaction(
    from_address,
    qualifier_change_address,
    qualifier,
    addresses,
    change_quantity=1,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    if not addresses:
        raise Exception('addresses must include at least one address.')

    operation_payload = {
        'untag_addresses': {
            'qualifier': str(qualifier),
            'addresses': [str(address) for address in addresses],
            'change_quantity': float(Decimal(str(change_quantity))),
        }
    }

    burn_amount = Decimal('0.1') * Decimal(str(len(addresses)))
    owner_change_output = (
        qualifier_change_address,
        {
            'transfer': {
                str(qualifier): float(Decimal(str(change_quantity))),
            }
        }
    )

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=qualifier_change_address,
        operation_payload=operation_payload,
        burn_amount_evr=burn_amount,
        burn_address=BURN_ADDRESS_TAG,
        authorization_asset_name=str(qualifier),
        owner_token_change_output=owner_change_output,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )


def create_and_send_freeze_addresses_transaction(
    from_address,
    owner_change_address,
    asset_name,
    addresses,
    owner_change_quantity=1,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    operation_payload = {
        'freeze_addresses': {
            'asset_name': str(asset_name),
            'addresses': [str(address) for address in addresses],
        }
    }

    owner_change_output = (
        owner_change_address,
        {
            'transfer': {
                _owner_token_name(asset_name): float(Decimal(str(owner_change_quantity))),
            }
        }
    )

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=owner_change_address,
        operation_payload=operation_payload,
        authorization_asset_name=_owner_token_name(asset_name),
        owner_token_change_output=owner_change_output,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )


def create_and_send_unfreeze_addresses_transaction(
    from_address,
    owner_change_address,
    asset_name,
    addresses,
    owner_change_quantity=1,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    operation_payload = {
        'unfreeze_addresses': {
            'asset_name': str(asset_name),
            'addresses': [str(address) for address in addresses],
        }
    }

    owner_change_output = (
        owner_change_address,
        {
            'transfer': {
                _owner_token_name(asset_name): float(Decimal(str(owner_change_quantity))),
            }
        }
    )

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=owner_change_address,
        operation_payload=operation_payload,
        authorization_asset_name=_owner_token_name(asset_name),
        owner_token_change_output=owner_change_output,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )


def create_and_send_freeze_asset_transaction(
    from_address,
    owner_change_address,
    asset_name,
    owner_change_quantity=1,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    operation_payload = {
        'freeze_asset': {
            'asset_name': str(asset_name),
        }
    }

    owner_change_output = (
        owner_change_address,
        {
            'transfer': {
                _owner_token_name(asset_name): float(Decimal(str(owner_change_quantity))),
            }
        }
    )

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=owner_change_address,
        operation_payload=operation_payload,
        authorization_asset_name=_owner_token_name(asset_name),
        owner_token_change_output=owner_change_output,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )


def create_and_send_unfreeze_asset_transaction(
    from_address,
    owner_change_address,
    asset_name,
    owner_change_quantity=1,
    fee_evr=None,
    fee_conf_target=DEFAULT_FEE_CONF_TARGET,
    fee_estimate_mode=DEFAULT_FEE_ESTIMATE_MODE,
    locktime=0,
    replaceable=False,
):
    operation_payload = {
        'unfreeze_asset': {
            'asset_name': str(asset_name),
        }
    }

    owner_change_output = (
        owner_change_address,
        {
            'transfer': {
                _owner_token_name(asset_name): float(Decimal(str(owner_change_quantity))),
            }
        }
    )

    return create_and_send_asset_operation_transaction(
        from_address=from_address,
        operation_address=owner_change_address,
        operation_payload=operation_payload,
        authorization_asset_name=_owner_token_name(asset_name),
        owner_token_change_output=owner_change_output,
        fee_evr=fee_evr,
        fee_conf_target=fee_conf_target,
        fee_estimate_mode=fee_estimate_mode,
        locktime=locktime,
        replaceable=replaceable,
    )

def create_raw_transaction(inputs, outputs, locktime=0, replaceable=False):
    """
    Create a raw transaction on the Evrmore network.
    
    Args:
        inputs (list): List of dicts with 'txid' and 'vout' keys
                       Example: [{"txid": "...", "vout": 0}]
        outputs (dict): Dict mapping addresses to amounts or operation objects
                Example: {"EVR_ADDRESS": 0.5}
        locktime (int): Optional locktime value
        replaceable (bool): Optional BIP125 RBF flag
    
    Returns:
        str: Raw transaction hex string
    
    Raises:
        Exception: If RPC call fails
    """
    try:
        if locktime or replaceable:
            raw_tx = RPC.createrawtransaction(inputs, outputs, locktime, replaceable)
        else:
            raw_tx = RPC.createrawtransaction(inputs, outputs)
        return raw_tx
    except Exception as e:
        raise Exception(f"Failed to create raw transaction: {str(e)}")
    
