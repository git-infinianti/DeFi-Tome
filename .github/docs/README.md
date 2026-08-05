# Internal Documentation

This directory contains maintainer-facing implementation references and
historical feature notes. Keep non-public Markdown documentation here rather
than adding standalone Markdown files at the repository root.

## Contents

### Evrmore Assets

- [Asset integration summary](ASSET_INTEGRATION_SUMMARY.md)
- [Asset type reference](EVRMORE_ASSET_TYPES.md)
- [Asset integration security summary](SECURITY_SUMMARY.md)

### NFTs

- [NFT implementation checklist](NFT_IMPLEMENTATION_COMPLETE.md)
- [NFT frontend implementation summary](NFT_FRONTEND_IMPLEMENTATION.md)
- [NFT quick reference](NFT_QUICK_REFERENCE.md)

### Protocol Integrations

- [RIP-0010 address metadata tags](RIP-0010_ADDRESS_METADATA_TAGS.md)

### RPC Operations

- [Evrmore command cheatsheet](commands-cheatsheet.md)

The command cheatsheet is machine-validated by
`scripts/verify_rpc_cheatsheet.py`; keep its command-list format intact.

## Frontend Consistency

When adding a screen to an existing app, begin with the closest existing
template in that app and preserve its theme class, CSS variables, typography,
header/navigation structure, cards, and button states. Do not introduce a
one-off visual system for a feature unless the change is an intentional,
documented product-wide design decision. Check the new screen in both light and
dark themes before considering it complete.