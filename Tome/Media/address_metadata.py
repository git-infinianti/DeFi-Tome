"""Issuance and verification services for RIP-0010 address metadata tags."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from django.utils import timezone

from Media.kubo_api import KuboAPIUploader
from Media.models import AddressMetadataTag
from Wallet.models import WalletAddress
from Wallet.rip10 import (
    MetadataValidationResult,
    RIP10ValidationError,
    address_crc32,
    build_address_metadata_asset,
    build_signed_metadata,
    metadata_signature_hash,
    normalize_address,
    parse_address_metadata_asset,
    validate_metadata,
)
from Wallet.rpc import RPC, create_and_send_issue_unique_transaction
from Wallet.wallet import Wallet
from Tome.rpc_client import get_current_network_mode


class AddressMetadataTagError(Exception):
    """Raised when a RIP-0010 tag cannot be issued or verified."""


class AddressMetadataTagIssuanceError(AddressMetadataTagError):
    """An issuance error that retains the persisted attempt record."""

    def __init__(self, message: str, tag: AddressMetadataTag):
        super().__init__(message)
        self.tag = tag


@dataclass(frozen=True)
class AddressMetadataVerification:
    """Verification state for one address metadata asset and its IPFS payload."""

    asset_name: str
    target_address: str
    tag_type: str | None
    ipfs_cid: str
    metadata: dict[str, Any] | None
    validation: MetadataValidationResult | None
    signature_valid: bool | None
    error: str = ""

    @property
    def is_valid(self) -> bool:
        return bool(
            self.validation
            and self.validation.is_valid
            and self.signature_valid is True
            and not self.error
        )


def list_controlled_addresses(user) -> list[str]:
    """Return addresses currently controlled by the user's managed wallet."""
    return [address for address, _wif in _controlled_address_wifs(user)]


def issue_address_metadata_tag(
    *,
    user,
    main_asset: str,
    tag_type: str,
    target_address: str,
    tag_payload: Mapping[str, Any],
    revision: str = "",
    uploader: KuboAPIUploader | None = None,
) -> AddressMetadataTag:
    """Upload, issue, and record a signed RIP-0010 unique asset tag."""
    try:
        target_address = normalize_address(target_address)
        asset = build_address_metadata_asset(main_asset, tag_type, target_address, revision)
    except RIP10ValidationError as exc:
        raise AddressMetadataTagError(str(exc)) from exc

    existing_attempt = AddressMetadataTag.objects.filter(
        user=user,
        asset_name=asset.asset_name,
        status__in=(
            AddressMetadataTag.Status.PENDING,
            AddressMetadataTag.Status.BROADCAST,
            AddressMetadataTag.Status.BROADCAST_UNKNOWN,
        ),
    ).exists()
    if existing_attempt:
        raise AddressMetadataTagError(
            f"A nonterminal issuance record already exists for {asset.asset_name}."
        )

    target_wif = _wif_for_controlled_address(user, target_address)
    tag = dict(tag_payload)
    try:
        signature_hash = metadata_signature_hash(tag)
        signature = _sign_metadata_message(target_address, target_wif, signature_hash)
        metadata = build_signed_metadata(tag, signature)
    except RIP10ValidationError as exc:
        raise AddressMetadataTagError(str(exc)) from exc

    local_validation = validate_metadata(asset.asset_name, target_address, metadata)
    if not local_validation.is_valid:
        raise AddressMetadataTagError("Metadata does not satisfy address profile integrity requirements.")
    if _verify_metadata_signature(target_address, metadata) is not True:
        raise AddressMetadataTagError("Unable to verify the metadata signature for the tagged address.")

    tag_record = AddressMetadataTag.objects.create(
        user=user,
        target_address=target_address,
        main_asset=asset.main_asset,
        tag_type=asset.tag_type,
        revision=asset.revision,
        asset_name=asset.asset_name,
        metadata=metadata,
        status=AddressMetadataTag.Status.PENDING,
        signature_verified=True,
    )

    try:
        metadata_bytes = json.dumps(
            metadata,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        upload_result = (uploader or KuboAPIUploader()).upload_bytes(
            metadata_bytes,
            file_name=f"{asset.asset_name.replace('#', '_')}.json",
            pin=True,
            cid_version=0,
        )
        tag_record.ipfs_cid = upload_result.cid
        tag_record.save(update_fields=("ipfs_cid", "updated_at"))
    except Exception as exc:
        _mark_attempt_failure(tag_record, AddressMetadataTag.Status.FAILED, exc)
        raise AddressMetadataTagIssuanceError("Unable to upload profile metadata to IPFS.", tag_record) from exc

    try:
        funding_address, funding_wif = _find_funding_address(user, asset.main_asset)
        tag_record.funding_address = funding_address
        tag_record.save(update_fields=("funding_address", "updated_at"))
    except Exception as exc:
        _mark_attempt_failure(tag_record, AddressMetadataTag.Status.FAILED, exc)
        raise AddressMetadataTagIssuanceError(
            f"No controlled address holds the {asset.main_asset}! owner token.",
            tag_record,
        ) from exc

    try:
        transaction = create_and_send_issue_unique_transaction(
            from_address=funding_address,
            issuer_address=target_address,
            root_name=asset.main_asset,
            asset_tags=[asset.unique_tag],
            ipfs_hashes=[tag_record.ipfs_cid],
            owner_change_address=funding_address,
            wif_keys=[funding_wif],
        )
        transaction_id = str(transaction.get("txid") or "").strip()
        if not transaction_id:
            raise AddressMetadataTagError("The node did not return a transaction ID.")
    except Exception as exc:
        _mark_attempt_failure(tag_record, AddressMetadataTag.Status.BROADCAST_UNKNOWN, exc)
        raise AddressMetadataTagIssuanceError(
            "Profile broadcast did not return a transaction ID; verify the asset before retrying.",
            tag_record,
        ) from exc

    tag_record.transaction_id = transaction_id
    tag_record.status = AddressMetadataTag.Status.BROADCAST
    tag_record.error_message = ""
    tag_record.save(update_fields=("transaction_id", "status", "error_message", "updated_at"))
    return tag_record


def discover_address_metadata_tags(
    address: str,
    *,
    uploader: KuboAPIUploader | None = None,
) -> list[AddressMetadataVerification]:
    """Discover and verify RIP-0010 assets currently held by ``address``."""
    try:
        target_address = normalize_address(address)
        balances = RPC.listassetbalancesbyaddress(target_address)
    except Exception as exc:
        raise AddressMetadataTagError("Unable to read address asset balances from the Evrmore node.") from exc

    expected_checksum = address_crc32(target_address)
    verifications: list[AddressMetadataVerification] = []
    for asset_name in _asset_names_with_positive_balance(balances):
        try:
            parsed = parse_address_metadata_asset(asset_name)
        except RIP10ValidationError:
            continue

        if parsed.address_hash != expected_checksum:
            continue

        try:
            asset_data = RPC.getassetdata(parsed.asset_name)
            ipfs_cid = _asset_ipfs_cid(asset_data)
            if not ipfs_cid:
                raise AddressMetadataTagError("The unique asset has no IPFS metadata CID.")
            verification = verify_address_metadata_tag(
                asset_name=parsed.asset_name,
                target_address=target_address,
                ipfs_cid=ipfs_cid,
                uploader=uploader,
            )
        except Exception as exc:
            verification = AddressMetadataVerification(
                asset_name=parsed.asset_name,
                target_address=target_address,
                tag_type=parsed.tag_type,
                ipfs_cid="",
                metadata=None,
                validation=None,
                signature_valid=None,
                error=_safe_error_message(exc),
            )
        verifications.append(verification)

    return verifications


def verify_address_metadata_tag(
    *,
    asset_name: str,
    target_address: str,
    ipfs_cid: str,
    uploader: KuboAPIUploader | None = None,
) -> AddressMetadataVerification:
    """Validate one RIP-0010 unique asset and its IPFS metadata payload."""
    try:
        parsed = parse_address_metadata_asset(asset_name)
        target_address = normalize_address(target_address)
        metadata = (uploader or KuboAPIUploader()).download_json(ipfs_cid)
        validation = validate_metadata(parsed.asset_name, target_address, metadata)
        signature_valid = _verify_metadata_signature(target_address, metadata)
        return AddressMetadataVerification(
            asset_name=parsed.asset_name,
            target_address=target_address,
            tag_type=parsed.tag_type,
            ipfs_cid=ipfs_cid,
            metadata=metadata,
            validation=validation,
            signature_valid=signature_valid,
            error="",
        )
    except Exception as exc:
        return AddressMetadataVerification(
            asset_name=str(asset_name),
            target_address=str(target_address),
            tag_type=None,
            ipfs_cid=str(ipfs_cid),
            metadata=None,
            validation=None,
            signature_valid=None,
            error=_safe_error_message(exc),
        )


def verify_stored_address_metadata_tag(
    tag_record: AddressMetadataTag,
    *,
    uploader: KuboAPIUploader | None = None,
) -> AddressMetadataVerification:
    """Verify a locally recorded tag and persist the latest verification result."""
    verification = verify_address_metadata_tag(
        asset_name=tag_record.asset_name,
        target_address=tag_record.target_address,
        ipfs_cid=tag_record.ipfs_cid,
        uploader=uploader,
    )
    tag_record.signature_verified = verification.signature_valid
    tag_record.last_verified_at = timezone.now()
    tag_record.verification_error = verification.error or "; ".join(
        verification.validation.errors if verification.validation else ()
    )
    tag_record.save(
        update_fields=(
            "signature_verified",
            "last_verified_at",
            "verification_error",
            "updated_at",
        )
    )
    return verification


def _controlled_address_wifs(user) -> list[tuple[str, str]]:
    user_wallet = getattr(user, "user_wallet", None)
    if user_wallet is None:
        raise AddressMetadataTagError("Create a managed wallet before creating an address profile.")

    addresses: list[tuple[str, str]] = []
    seen_addresses: set[str] = set()
    wallet_addresses = WalletAddress.objects.filter(
        wallet=user_wallet,
        network_mode=get_current_network_mode(),
    ).order_by(
        "account", "is_change", "index"
    )
    for wallet_address in wallet_addresses:
        address = normalize_address(wallet_address.address)
        wif = str(wallet_address.wif or "").strip()
        if address not in seen_addresses and wif:
            addresses.append((address, wif))
            seen_addresses.add(address)

    if addresses:
        return addresses

    wallet = Wallet(
        user_wallet.entropy,
        user_wallet.passphrase,
        network_mode=get_current_network_mode(),
    )
    address = wallet.get_address()
    wif = wallet.get_wif()
    WalletAddress.objects.get_or_create(
        wallet=user_wallet,
        network_mode=get_current_network_mode(),
        account=0,
        index=0,
        is_change=False,
        defaults={
            "address": address,
            "wif": wif,
        },
    )
    return [(address, wif)]


def _wif_for_controlled_address(user, target_address: str) -> str:
    for address, wif in _controlled_address_wifs(user):
        if address == target_address:
            return wif
    raise AddressMetadataTagError("The tagged address must be controlled by your managed wallet.")


def _find_funding_address(user, main_asset: str) -> tuple[str, str]:
    owner_token = f"{main_asset}!"
    successful_queries = 0
    for address, wif in _controlled_address_wifs(user):
        try:
            balances = RPC.listassetbalancesbyaddress(address)
            successful_queries += 1
        except Exception:
            continue

        if _asset_balance(balances, owner_token) > 0:
            return address, wif

    if not successful_queries:
        raise AddressMetadataTagError("Unable to read managed-wallet asset balances from the Evrmore node.")
    raise AddressMetadataTagError(f"No managed wallet address holds the {owner_token} owner token.")


def _asset_balance(balances: Any, asset_name: str) -> Decimal:
    if isinstance(balances, Mapping):
        for candidate_name, amount in balances.items():
            if str(candidate_name).upper() == asset_name.upper():
                return _as_decimal(amount)
        return Decimal("0")

    if isinstance(balances, list):
        for item in balances:
            if not isinstance(item, Mapping):
                continue
            candidate_name = item.get("assetName", item.get("assetname", item.get("asset")))
            if candidate_name and str(candidate_name).upper() == asset_name.upper():
                return _as_decimal(item.get("balance", item.get("amount", 0)))
    return Decimal("0")


def _asset_names_with_positive_balance(balances: Any) -> list[str]:
    if isinstance(balances, Mapping):
        return [
            str(asset_name)
            for asset_name, amount in balances.items()
            if _as_decimal(amount) > 0
        ]

    names: list[str] = []
    if isinstance(balances, list):
        for item in balances:
            if not isinstance(item, Mapping):
                continue
            asset_name = item.get("assetName", item.get("assetname", item.get("asset")))
            amount = item.get("balance", item.get("amount", 0))
            if asset_name and _as_decimal(amount) > 0:
                names.append(str(asset_name))
    return names


def _asset_ipfs_cid(asset_data: Any) -> str:
    if not isinstance(asset_data, Mapping):
        return ""
    for field_name in ("ipfs_hash", "ipfsHash", "ipfs"):
        cid = str(asset_data.get(field_name) or "").strip()
        if cid:
            return cid
    return ""


def _as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _sign_metadata_message(address: str, wif: str, message: str) -> str:
    signing_errors: list[Exception] = []
    try:
        signature = RPC.signmessagewithprivkey(wif, message)
        if signature:
            return str(signature)
    except Exception as exc:
        signing_errors.append(exc)

    try:
        signature = RPC.signmessage(address, message)
        if signature:
            return str(signature)
    except Exception as exc:
        signing_errors.append(exc)

    try:
        RPC.importprivkey(wif, f"rip10-{address}", False)
    except Exception as exc:
        signing_errors.append(exc)

    try:
        signature = RPC.signmessage(address, message)
        if signature:
            return str(signature)
    except Exception as exc:
        signing_errors.append(exc)

    cause = signing_errors[-1] if signing_errors else None
    raise AddressMetadataTagError("Unable to sign metadata with the tagged address.") from cause


def _verify_metadata_signature(address: str, metadata: Mapping[str, Any]) -> bool | None:
    tag = metadata.get("tag") if isinstance(metadata, Mapping) else None
    signature_data = metadata.get("metadata_signature") if isinstance(metadata, Mapping) else None
    if not isinstance(tag, Mapping) or not isinstance(signature_data, Mapping):
        return False

    signature = str(signature_data.get("signature") or "").strip()
    signature_hash = str(signature_data.get("signature_hash") or "").strip()
    if not signature or not signature_hash:
        return False

    try:
        return bool(RPC.verifymessage(address, signature, signature_hash))
    except Exception:
        return None


def _mark_attempt_failure(tag_record: AddressMetadataTag, status: str, exc: Exception) -> None:
    tag_record.status = status
    tag_record.error_message = _safe_error_message(exc)
    tag_record.save(update_fields=("status", "error_message", "updated_at"))


def _safe_error_message(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    return message[:2_000]