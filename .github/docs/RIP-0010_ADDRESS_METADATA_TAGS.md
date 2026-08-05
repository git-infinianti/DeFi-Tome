# RIP-0010 Address Metadata Tags

## Source And Scope

Source: [RIP-0010](https://github.com/RavenProject/rips/blob/master/rip-0010.mediawiki), retrieved 2026-08-04. The proposal is a draft process RIP that defines a portable convention for associating an address with IPFS-backed metadata through a unique asset.

RIP-0010 is the common envelope. RIP-0011 (encryption), RIP-0012 (address names), and RIP-0013 (identity) are separate draft applications of that envelope. This implementation supports the base protocol and the public metadata structures for `ANT`, `PGP`/`AET`, and `AIT`.

## Product Terminology

The public DeFi Tome product name is **Address Profiles**. It describes the
feature as a whole: address names, encryption keys, identity records, and custom
metadata. Keep RIP identifiers in protocol documentation, source code, tests,
and operational references, but do not expose them in browser-facing labels,
messages, page titles, or copy.

## Protocol Notes

| Concern | RIP-0010 convention | DeFi Tome behavior |
| --- | --- | --- |
| Unique asset | `MAIN_ASSET#TAG_<address_crc32>` | Builds and parses this form in `Wallet.rip10`. |
| Main asset | At most 10 characters, with the owner token available to the issuer | Accepts 3-10 uppercase letters, digits, periods, and underscores, then requires `MAIN_ASSET!` in a controlled wallet address. |
| Tag identifier | Three letters | Validates and normalizes it to uppercase. |
| Address checksum | Eight-character CRC32 of the address | Uses uppercase hexadecimal CRC32 over the ASCII address text. |
| Reserved suffix | Seven characters are reserved after the base 23-character form | Supports an optional seven-character alphanumeric revision, allowing 30-character asset names. This is useful for RIP-0013 replacement tags. |
| Metadata | IPFS content referenced by the unique asset | Pins canonical JSON through Kubo as CIDv0 for legacy asset-RPC compatibility. |
| Ownership proof | Metadata can carry a signature from the tagged address | Signs the SHA256 of the deterministic `tag` object and verifies it before issuance and during lookup. |

The asset itself is held by the tagged address. The checksum is only a short routing/checksum aid, not a cryptographic proof of address ownership.

## Supported Metadata Envelopes

All metadata uses this outer form:

```json
{
  "tag": { "...": "application fields" },
  "metadata_signature": {
    "signature_hash": "sha256 of the canonical tag JSON",
    "signature": "Evrmore/Ravencoin message signature"
  }
}
```

The implementation canonicalizes a tag as UTF-8 JSON with sorted keys and compact separators before calculating `signature_hash`. That makes newly issued tags deterministic. The RIP does not specify a canonical JSON serialization, so signatures from external implementations that hash a differently serialized JSON object may require an interoperability adapter.

| Asset tag | Metadata `tag_type` | Accepted fields |
| --- | --- | --- |
| `ANT` | `ANT` | `ravencoin_address`, `address_name`, `address_name_mime`, optional base64 `icon` |
| `PGP` | `AET` | `ravencoin_address`, `pgp_pubkey` |
| `AIT` | `AIT` | `ravencoin_address`, encryption `algorithm`, encrypted `identity_document` CID |
| Custom | Same three-letter identifier | Additional JSON fields, while the implementation owns `tag_type` and `ravencoin_address` |

The `PGP` asset / `AET` payload distinction is intentional and follows RIP-0011.

## Issuance Lifecycle

1. The user selects an address controlled by their managed wallet.
2. The service builds the selected metadata payload and signs it with that address.
3. It verifies the signature locally through the configured Evrmore node.
4. It creates an `AddressMetadataTag` attempt record, then uploads the canonical JSON to Kubo.
5. It finds a controlled address holding the main-asset owner token.
6. It issues one unique asset with a 5 EVR burn through the existing raw asset-operation builder, passing the funding WIF explicitly.
7. It records the CID, transaction ID, and status.

`broadcast_unknown` is intentionally conservative. An RPC exception after submission may still mean the node accepted the transaction, so the UI asks the user to verify the asset before retrying.

## Discovery And Verification

For an address lookup, DeFi Tome:

1. Reads assets with positive balances at the address.
2. Keeps only names that parse as RIP-0010 and whose CRC32 matches that address.
3. Reads the on-chain asset metadata CID.
4. Fetches at most 1 MiB from the configured Kubo `/api/v0/cat` endpoint.
5. Checks the metadata address, tag type, canonical SHA256 hash, and blockchain message signature.

The lookup does not treat an IPFS payload or CRC32 match as an identity claim unless the message signature verifies.

## Operational Requirements

- A reachable Kubo API configured through `IPFS_STORAGE_API_URL`.
- An Evrmore node with asset index data and RPC support for `listassetbalancesbyaddress`, `getassetdata`, `signmessage` or `signmessagewithprivkey`, and `verifymessage`.
- A main asset already issued to a controlled address, including its `!` owner token.
- Sufficient EVR for the network fee and the 5 EVR unique-asset burn.

## Security Boundaries

- Issuance is limited to addresses controlled by the signed-in managed wallet so the metadata signature represents address ownership.
- Raw unique-asset transactions receive an explicit WIF; they do not depend on a node-wallet signature fallback.
- Metadata CIDs and public key material are public. Do not place secrets, unencrypted identity documents, or PGP private keys in a tag payload.
- If the node lacks `signmessagewithprivkey`, the implementation falls back to its existing local-node `signmessage` pattern and may import the WIF into that node. Production deployments should use an isolated, access-controlled node or add an offline message signer.
- RIP-0011 key-pair management, PGP private-key custody, encrypted asset-file workflows, and RIP-0013 identity-document encryption/key distribution are not standardized by RIP-0010 itself. The UI accepts their public metadata inputs but deliberately does not handle private keys or identity documents server-side.

## Implementation Map

- `Tome/Wallet/rip10.py`: naming, CRC32, typed metadata builders, and local validation.
- `Tome/Wallet/rpc.py`: explicit WIF propagation for unique-asset issuance.
- `Tome/Media/kubo_api.py`: bounded metadata retrieval from Kubo.
- `Tome/Media/address_metadata.py`: issuance, discovery, signature checks, and attempt state handling.
- `Tome/Media/models.py`: durable public tag records.
- `Tome/Media/templates/media/address_metadata_*.html`: issuance, lookup, and verification UI.

## Test Coverage

- Name construction, parse round trips, checksum binding, revision limits, and `PGP`/`AET` compatibility.
- Explicit signing-key propagation into unique-asset issuance.
- Kubo metadata retrieval boundaries.
- Issuance, CIDv0 selection, owner-token selection, and discovery filtering with mocked node/Kubo boundaries.
- Authenticated create-route payload construction.