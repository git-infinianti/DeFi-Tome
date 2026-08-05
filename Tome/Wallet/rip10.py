"""RIP-0010 address metadata tag naming and metadata helpers."""

from __future__ import annotations

import hashlib
import json
import re
import zlib
from dataclasses import dataclass
from typing import Any, Mapping


RIP10_MAX_MAIN_ASSET_LENGTH = 10
RIP10_BASE_ASSET_NAME_LENGTH = 23
RIP10_MAX_ASSET_NAME_LENGTH = 30
RIP10_STANDARD_TAG_TYPES = frozenset({"ANT", "PGP", "AIT"})

_MAIN_ASSET_PATTERN = re.compile(r"^[A-Z0-9._]{3,10}$")
_TAG_TYPE_PATTERN = re.compile(r"^[A-Z]{3}$")
_REVISION_PATTERN = re.compile(r"^[A-Z0-9]{0,7}$")
_UNIQUE_TAG_PATTERN = re.compile(
    r"^(?P<tag_type>[A-Z]{3})_(?P<address_hash>[0-9A-F]{8})(?P<revision>[A-Z0-9]{0,7})$"
)


class RIP10ValidationError(ValueError):
    """Raised when data cannot be represented as a RIP-0010 tag."""


@dataclass(frozen=True)
class AddressMetadataAsset:
    """The parsed components of a RIP-0010 unique asset name."""

    main_asset: str
    tag_type: str
    address_hash: str
    revision: str = ""

    @property
    def unique_tag(self) -> str:
        return f"{self.tag_type}_{self.address_hash}{self.revision}"

    @property
    def asset_name(self) -> str:
        return f"{self.main_asset}#{self.unique_tag}"


@dataclass(frozen=True)
class MetadataValidationResult:
    """Local verification results for metadata retrieved from a RIP-0010 tag."""

    checksum_valid: bool
    metadata_address_valid: bool
    metadata_type_valid: bool
    signature_hash_valid: bool
    errors: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


def normalize_main_asset(main_asset: str) -> str:
    """Normalize and validate the main-asset portion of a RIP-0010 name."""
    normalized = str(main_asset or "").strip().upper()
    if not _MAIN_ASSET_PATTERN.fullmatch(normalized):
        raise RIP10ValidationError(
            "Main asset names must be 3-10 uppercase letters, digits, periods, or underscores."
        )
    return normalized


def normalize_tag_type(tag_type: str) -> str:
    """Normalize and validate a three-letter RIP-0010 tag identifier."""
    normalized = str(tag_type or "").strip().upper()
    if not _TAG_TYPE_PATTERN.fullmatch(normalized):
        raise RIP10ValidationError("Tag types must contain exactly three uppercase letters.")
    return normalized


def normalize_revision(revision: str | None = "") -> str:
    """Normalize the optional seven-character unique-tag revision suffix."""
    normalized = str(revision or "").strip().upper()
    if not _REVISION_PATTERN.fullmatch(normalized):
        raise RIP10ValidationError("Revision suffixes may contain up to seven uppercase letters or digits.")
    return normalized


def normalize_address(address: str) -> str:
    """Return an address suitable for deterministic CRC32 calculation."""
    normalized = str(address or "").strip()
    if not normalized:
        raise RIP10ValidationError("A Ravencoin or Evrmore address is required.")

    try:
        normalized.encode("ascii")
    except UnicodeEncodeError as exc:
        raise RIP10ValidationError("Addresses must contain only ASCII characters.") from exc

    if any(character.isspace() for character in normalized):
        raise RIP10ValidationError("Addresses must not contain whitespace.")
    return normalized


def address_crc32(address: str) -> str:
    """Return the eight-character uppercase CRC32 checksum required by RIP-0010."""
    normalized = normalize_address(address)
    checksum = zlib.crc32(normalized.encode("ascii")) & 0xFFFFFFFF
    return f"{checksum:08X}"


def build_address_metadata_asset(
    main_asset: str,
    tag_type: str,
    address: str,
    revision: str | None = "",
) -> AddressMetadataAsset:
    """Build a validated RIP-0010 address metadata asset descriptor."""
    asset = AddressMetadataAsset(
        main_asset=normalize_main_asset(main_asset),
        tag_type=normalize_tag_type(tag_type),
        address_hash=address_crc32(address),
        revision=normalize_revision(revision),
    )
    if len(asset.asset_name) > RIP10_MAX_ASSET_NAME_LENGTH:
        raise RIP10ValidationError(
            f"Address profile asset names cannot exceed {RIP10_MAX_ASSET_NAME_LENGTH} characters."
        )
    return asset


def parse_address_metadata_asset(asset_name: str) -> AddressMetadataAsset:
    """Parse a RIP-0010 asset name without asserting the holder address."""
    normalized = str(asset_name or "").strip().upper()
    main_asset, separator, unique_tag = normalized.partition("#")
    if not separator or "#" in unique_tag:
        raise RIP10ValidationError("Address metadata assets must use MAIN_ASSET#TAG_CRC32 form.")

    main_asset = normalize_main_asset(main_asset)
    match = _UNIQUE_TAG_PATTERN.fullmatch(unique_tag)
    if not match:
        raise RIP10ValidationError("Unique asset suffix does not match RIP-0010 TAG_CRC32 format.")

    parsed = AddressMetadataAsset(
        main_asset=main_asset,
        tag_type=match.group("tag_type"),
        address_hash=match.group("address_hash"),
        revision=match.group("revision"),
    )
    if len(parsed.asset_name) > RIP10_MAX_ASSET_NAME_LENGTH:
        raise RIP10ValidationError(
            f"Address profile asset names cannot exceed {RIP10_MAX_ASSET_NAME_LENGTH} characters."
        )
    return parsed


def asset_matches_address(asset_name: str, address: str) -> bool:
    """Return whether a RIP-0010 asset checksum is bound to ``address``."""
    return parse_address_metadata_asset(asset_name).address_hash == address_crc32(address)


def canonical_tag_json(tag: Mapping[str, Any]) -> bytes:
    """Serialize a tag object deterministically before calculating its SHA256 hash."""
    if not isinstance(tag, Mapping):
        raise RIP10ValidationError("Tag metadata must be a JSON object.")

    try:
        return json.dumps(
            dict(tag),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RIP10ValidationError("Tag metadata must be JSON serializable.") from exc


def metadata_signature_hash(tag: Mapping[str, Any]) -> str:
    """Calculate the SHA256 hash of a canonical RIP-0010 tag object."""
    return hashlib.sha256(canonical_tag_json(tag)).hexdigest()


def build_signed_metadata(tag: Mapping[str, Any], signature: str) -> dict[str, Any]:
    """Wrap a tag object with the RIP-0010 metadata signature structure."""
    normalized_signature = str(signature or "").strip()
    if not normalized_signature:
        raise RIP10ValidationError("A metadata signature is required.")

    tag_payload = dict(tag)
    return {
        "tag": tag_payload,
        "metadata_signature": {
            "signature_hash": metadata_signature_hash(tag_payload),
            "signature": normalized_signature,
        },
    }


def build_address_name_tag(
    address: str,
    address_name: str,
    address_name_mime: str = "text/x-markdown; charset=UTF-8",
    icon: str | None = None,
) -> dict[str, Any]:
    """Build the RIP-0012 address-name tag payload used by an ANT asset."""
    normalized_name = str(address_name or "").strip()
    normalized_mime = str(address_name_mime or "").strip()
    if not normalized_name:
        raise RIP10ValidationError("An address name is required for ANT metadata.")
    if not normalized_mime:
        raise RIP10ValidationError("An address-name MIME type is required for ANT metadata.")

    payload: dict[str, Any] = {
        "tag_type": "ANT",
        "ravencoin_address": normalize_address(address),
        "address_name": normalized_name,
        "address_name_mime": normalized_mime,
    }
    if icon:
        payload["icon"] = str(icon)
    return payload


def build_encryption_tag(address: str, pgp_public_key: str) -> dict[str, str]:
    """Build the RIP-0011 AET payload carried by a PGP address metadata asset."""
    normalized_key = str(pgp_public_key or "").strip()
    if not normalized_key:
        raise RIP10ValidationError("A PGP public key is required for PGP metadata.")

    return {
        "tag_type": "AET",
        "ravencoin_address": normalize_address(address),
        "pgp_pubkey": normalized_key,
    }


def build_identity_tag(address: str, algorithm: str, identity_document: str) -> dict[str, str]:
    """Build the RIP-0013 identity-tag payload carried by an AIT asset."""
    normalized_algorithm = str(algorithm or "").strip()
    normalized_document = str(identity_document or "").strip()
    if not normalized_algorithm:
        raise RIP10ValidationError("An encryption algorithm is required for AIT metadata.")
    if not normalized_document:
        raise RIP10ValidationError("An encrypted identity-document CID is required for AIT metadata.")

    return {
        "tag_type": "AIT",
        "algorithm": normalized_algorithm,
        "ravencoin_address": normalize_address(address),
        "identity_document": normalized_document,
    }


def build_generic_tag(address: str, tag_type: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Build a custom RIP-0010 tag payload while reserving protocol-owned fields."""
    if not isinstance(metadata, Mapping):
        raise RIP10ValidationError("Custom metadata must be a JSON object.")

    reserved_keys = {"tag_type", "ravencoin_address"}
    supplied_reserved = reserved_keys.intersection(metadata)
    if supplied_reserved:
        names = ", ".join(sorted(supplied_reserved))
        raise RIP10ValidationError(f"Custom metadata must not override {names}.")

    payload = dict(metadata)
    payload["tag_type"] = normalize_tag_type(tag_type)
    payload["ravencoin_address"] = normalize_address(address)
    return payload


def validate_metadata(
    asset_name: str,
    address: str,
    metadata: Mapping[str, Any],
) -> MetadataValidationResult:
    """Validate the local RIP-0010 checksum and metadata integrity invariants."""
    errors: list[str] = []
    try:
        asset = parse_address_metadata_asset(asset_name)
        checksum_valid = asset.address_hash == address_crc32(address)
        if not checksum_valid:
            errors.append("The asset checksum does not match the holder address.")
    except RIP10ValidationError as exc:
        asset = None
        checksum_valid = False
        errors.append(str(exc))

    tag = metadata.get("tag") if isinstance(metadata, Mapping) else None
    signature = metadata.get("metadata_signature") if isinstance(metadata, Mapping) else None
    metadata_address_valid = isinstance(tag, Mapping) and tag.get("ravencoin_address") == normalize_address(address)
    if not metadata_address_valid:
        errors.append("Metadata does not identify the holder address.")

    expected_metadata_type = "AET" if asset and asset.tag_type == "PGP" else asset.tag_type if asset else None
    metadata_type_valid = isinstance(tag, Mapping) and tag.get("tag_type") == expected_metadata_type
    if not metadata_type_valid:
        errors.append("Metadata tag type does not match the unique asset type.")

    expected_hash = metadata_signature_hash(tag) if isinstance(tag, Mapping) else None
    signature_hash_valid = isinstance(signature, Mapping) and signature.get("signature_hash") == expected_hash
    if not signature_hash_valid:
        errors.append("Metadata signature hash does not match the tag payload.")

    return MetadataValidationResult(
        checksum_valid=checksum_valid,
        metadata_address_valid=metadata_address_valid,
        metadata_type_valid=metadata_type_valid,
        signature_hash_valid=signature_hash_valid,
        errors=tuple(errors),
    )