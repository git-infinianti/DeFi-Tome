# Evrmore Asset Type Integration

This document describes the integration of all Evrmore blockchain asset types into DeFi-Tome, including vault assets with toll features and NFTs.

## Overview

Evrmore blockchain has built-in DeFi tools and multiple asset types. This integration ensures proper support for all asset types:

- **Main Assets**: Standard fungible tokens
- **Sub-Assets**: Hierarchical tokens (e.g., PARENT/CHILD)
- **Unique Assets**: Collectibles with unique identifiers (e.g., TOKEN#123)
- **NFTs**: 1-of-1 assets with IPFS metadata (amount=1, non-reissuable)
- **Vault Assets**: Assets with transfer tolls/fees for DeFi operations
- **Messaging Channels**: Assets for on-chain messaging (contains ~)
- **Qualifiers**: Tagging/verification assets (starts with #)
- **Sub-Qualifiers**: Sub-categories of qualifiers (#PARENT/CHILD)
- **Restricted Assets**: KYC/regulated assets (starts with $)
- **Administrator Tokens**: Management tokens (ends with !)

## Asset Type Classification

The `classify_asset_type()` function in `Wallet/asset_tracking.py` automatically detects asset types based on:

1. **Symbol pattern matching** (for most types)
2. **RPC metadata** (for NFTs and vault assets)

### Symbol-Based Classification

```python
# Examples
'MYTOKEN'         -> Main Asset
'PARENT/CHILD'    -> Sub-Asset
'TOKEN#123'       -> Unique Asset
'CHANNEL~'        -> Messaging Channel
'#QUALIFIER'      -> Qualifier
'#QUAL/SUB'       -> Sub-Qualifier
'$RESTRICTED'     -> Restricted Asset
'ADMIN!'          -> Administrator Token
```

### Metadata-Based Classification

```python
# NFT (requires RPC data)
{
    'amount': 1,
    'reissuable': False,
    'has_ipfs': True
}

# Vault Asset (requires RPC data)
{
    'has_toll': True,
    'toll_percentage': 5.0,
    'toll_address': 'EVRxxx...'
}
```

## Database Models

### TrackedAsset (Wallet app)

Core model for tracking all asset types:

```python
# New fields for NFT/Vault support
ipfs_hash: IPFS hash for asset metadata
has_toll: Whether asset has transfer toll enabled
toll_percentage: Toll percentage for transfers (0-100)
toll_address: Address receiving toll payments
is_reissuable: Whether asset can be reissued
units: Decimal places for asset divisibility (0-8)
```

### VaultAsset (DeFi app)

Specialized model for vault assets with DeFi features:

- Toll/fee configuration
- Total toll collected tracking
- Transfer count tracking
- DeFi usage analytics

### VaultCollateral (DeFi app)

Collateral management for lending/borrowing:

- Collateral amount tracking
- Borrowed amount tracking
- Collateral ratio monitoring
- Liquidation threshold enforcement

### VaultEscrow (DeFi app)

Escrow for P2P swaps with vault assets:

- Multi-party escrow
- Toll deduction on release
- Expiration handling
- Status tracking

## RPC Methods

New RPC methods in `API/rpc.py`:

### Vault Asset Operations

```python
# Issue a vault asset with toll features
issue_vault_asset(
    asset_name='MYVAULT',
    qty=1000,
    toll_percentage=5.0,
    toll_address='EVRxxx...'
)

# Get toll information
get_vault_toll_info(asset_name='MYVAULT')
# Returns: {
#     'has_toll': True,
#     'toll_percentage': 5.0,
#     'toll_address': 'EVRxxx...',
#     'total_toll_collected': 123.45
# }
```

### NFT Operations

```python
# Issue an NFT
issue_nft_asset(
    asset_name='MYNFT',
    ipfs_hash='QmXxxx...',
    description='My NFT artwork'
)

# Verify ownership
verify_asset_ownership(
    asset_name='MYNFT',
    address='EVRxxx...'
)
```

## Usage Examples

### Creating a Vault Asset

```python
from Tome.API.rpc import evrmore_rpc

# Issue a vault asset with 2% toll
tx_hash = evrmore_rpc.issue_vault_asset(
    asset_name='DEFI_VAULT',
    qty=10000,
    to_address='EVRxxx...',
    units=8,
    reissuable=False,
    toll_percentage=2.0,
    toll_address='EVRxxx...'  # Address to receive tolls
)
```

### Tracking Assets with Metadata

```python
from Wallet.asset_tracking import sync_tracked_assets

# Sync with metadata fetching (slower but accurate)
asset_balances = {
    'MYTOKEN': Decimal('100.0'),
    'MYVAULT': Decimal('50.0'),
    'MYNFT': Decimal('1.0')
}

sync_tracked_assets(
    user=request.user,
    asset_balances=asset_balances,
    fetch_metadata=True  # Enables NFT/vault detection
)
```

### Working with Vault Collateral

```python
from DeFi.models import VaultAsset, VaultCollateral

# Create vault asset entry
vault = VaultAsset.objects.create(
    symbol='DEFI_VAULT',
    name='DeFi Vault Token',
    toll_percentage=2.0,
    toll_address='EVRxxx...'
)

# Lock collateral
collateral = VaultCollateral.objects.create(
    user=request.user,
    vault_asset=vault,
    collateral_amount=Decimal('1000.0'),
    collateral_ratio=150,  # 150%
    liquidation_threshold=120  # 120%
)

# Check if liquidatable
if collateral.is_liquidatable:
    # Trigger liquidation
    pass
```

## Asset Type-Specific Features

### Main Assets
- Standard fungible tokens
- Divisible (0-8 decimals)
- Reissuable or fixed supply
- Used for trading, liquidity pools

### Vault Assets
- Transfer tolls (fees) paid in EVR
- Toll goes to specified address
- Ideal for:
  - Revenue-generating DeFi protocols
  - NFT royalties (future: Evrmore Core V2)
  - Protocol fees
  - DAO treasuries

### NFTs
- Exactly 1 unit
- Non-reissuable
- IPFS metadata/image
- Unique collectibles
- Used in marketplace

### Messaging Channels
- On-chain communication
- Subscription-based
- Message broadcasting
- IPFS content hashes

### Qualifiers & Restricted Assets
- KYC/AML compliance
- Whitelisting
- Regulatory requirements
- Qualified investor verification

## Testing

Run asset type classification tests:

```bash
cd Tome
python manage.py test Wallet.test_asset_tracking
```

All asset types are validated in the test suite:
- Symbol-based classification
- Metadata-based classification (NFT, Vault)
- Edge cases and fallbacks

## Migration

Database migrations are in:
- `Wallet/migrations/0001_initial.py`
- `DeFi/migrations/0001_initial.py`

Apply migrations:

```bash
python manage.py migrate
```

## Admin Interface

All asset models are registered in Django admin:

- **Wallet Admin**: TrackedAsset, TrackedAssetHolding
- **DeFi Admin**: VaultAsset, VaultCollateral, VaultEscrow

Access at `/admin/` to manage assets.

## Future Enhancements

### Evrmore Core V2 Features
When Evrmore Core V2 is released with full toll support:

1. **NFT Royalties**: Automatic royalty payments on resale
2. **Enhanced Toll Configuration**: More granular fee structures
3. **Cross-Chain Bridges**: Asset tolls for bridge fees
4. **Governance Integration**: Toll-based voting mechanisms

### Planned Improvements
- Real-time toll tracking dashboard
- Vault asset analytics
- Automated collateral rebalancing
- Flash loan support for vault assets
- Multi-asset escrow contracts

## Security Considerations

1. **Toll Validation**: Always validate toll percentage (0-100%)
2. **Collateral Ratios**: Enforce minimum collateral requirements
3. **Escrow Timeouts**: Implement expiration handling
4. **IPFS Verification**: Validate IPFS hash formats
5. **RPC Resilience**: Handle RPC failures gracefully

## References

- [Evrmore Asset Overview](https://hans-schmidt.github.io/mastering_evrmore/current_tech_docs/evrmore_overview_of_assets.html)
- [Evrmore DeFi Roadmap](https://hans-schmidt.github.io/mastering_evrmore/roadmap_tech_docs/the_evrmore_defi_roadmap.html)
- [Evrmore RPC Documentation](https://github.com/EvrmoreOrg/Evrmore)

## Support

For questions or issues:
- Create GitHub issue
- Check documentation
- Join Discord community
