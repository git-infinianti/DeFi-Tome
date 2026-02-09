from decimal import Decimal
from django.db import transaction
from django.db.models import Sum

from .models import TrackedAsset, TrackedAssetHolding


def classify_asset_type(symbol: str, asset_data: dict = None) -> str:
    """
    Classify asset type based on symbol and optional RPC asset data.
    
    Args:
        symbol: Asset symbol/name
        asset_data: Optional dict from getassetdata RPC call
    
    Returns:
        Asset type constant from TrackedAsset
    """
    # Admin token
    if symbol.endswith('!'):
        return TrackedAsset.ASSET_TYPE_ADMIN
    
    # Restricted asset
    if symbol.startswith('$'):
        return TrackedAsset.ASSET_TYPE_RESTRICTED
    
    # Qualifier asset (starts with #)
    if symbol.startswith('#'):
        if '/' in symbol:
            return TrackedAsset.ASSET_TYPE_SUB_QUALIFIER
        return TrackedAsset.ASSET_TYPE_QUALIFIER
    
    # Messaging channel (contains ~)
    if '~' in symbol:
        return TrackedAsset.ASSET_TYPE_MESSAGING
    
    # Unique asset/NFT (contains # but doesn't start with it)
    if '#' in symbol:
        return TrackedAsset.ASSET_TYPE_UNIQUE
    
    # Check if it's a vault asset (has toll enabled) using RPC data
    if asset_data and asset_data.get('has_toll', False):
        return TrackedAsset.ASSET_TYPE_VAULT
    
    # Check if it's an NFT (amount = 1, not reissuable, has IPFS) using RPC data
    if asset_data:
        amount = asset_data.get('amount', 0)
        reissuable = asset_data.get('reissuable', True)
        has_ipfs = asset_data.get('has_ipfs', False)
        
        # NFT characteristics: exactly 1 unit, not reissuable, has IPFS
        if amount == 1 and not reissuable and has_ipfs:
            return TrackedAsset.ASSET_TYPE_NFT
    
    # Sub-asset (contains /)
    if '/' in symbol:
        return TrackedAsset.ASSET_TYPE_SUB
    
    # Default: main asset
    return TrackedAsset.ASSET_TYPE_MAIN


def sync_tracked_assets(user, asset_balances: dict, fetch_metadata: bool = False) -> None:
    """
    Persist tracked assets and user holdings from a balance dict.

    Args:
        user: Django User
        asset_balances: dict of {symbol: Decimal}
        fetch_metadata: Whether to fetch asset metadata from RPC (slower but more accurate)
    """
    if user is None:
        return

    asset_symbols = set(asset_balances.keys())

    with transaction.atomic():
        # Track current assets and holdings
        for symbol, amount in asset_balances.items():
            asset_data = None
            
            # Optionally fetch asset metadata from RPC for better classification
            if fetch_metadata:
                try:
                    from Tome.API.rpc import evrmore_rpc
                    asset_data = evrmore_rpc.get_asset_data(symbol)
                except Exception:
                    # If RPC fails, proceed without metadata
                    pass
            
            asset_type = classify_asset_type(symbol, asset_data)
            
            # Prepare defaults with basic info
            defaults = {'asset_type': asset_type}
            
            # Add metadata if available
            if asset_data:
                defaults['ipfs_hash'] = asset_data.get('ipfs_hash', '')
                defaults['has_toll'] = asset_data.get('has_toll', False)
                defaults['is_reissuable'] = asset_data.get('reissuable', True)
                defaults['units'] = asset_data.get('units', 0)
                
                # Extract toll info if present
                if asset_data.get('has_toll'):
                    defaults['toll_percentage'] = asset_data.get('toll_percentage', 0)
                    defaults['toll_address'] = asset_data.get('toll_address', '')
            
            asset, created = TrackedAsset.objects.get_or_create(
                symbol=symbol,
                defaults=defaults
            )
            
            # Update asset if it exists and data has changed
            if not created:
                update_fields = []
                
                if asset.asset_type != asset_type:
                    asset.asset_type = asset_type
                    update_fields.append('asset_type')
                
                if asset_data:
                    if asset.ipfs_hash != asset_data.get('ipfs_hash', ''):
                        asset.ipfs_hash = asset_data.get('ipfs_hash', '')
                        update_fields.append('ipfs_hash')
                    
                    if asset.has_toll != asset_data.get('has_toll', False):
                        asset.has_toll = asset_data.get('has_toll', False)
                        update_fields.append('has_toll')
                    
                    if asset.is_reissuable != asset_data.get('reissuable', True):
                        asset.is_reissuable = asset_data.get('reissuable', True)
                        update_fields.append('is_reissuable')
                    
                    if asset.units != asset_data.get('units', 0):
                        asset.units = asset_data.get('units', 0)
                        update_fields.append('units')
                
                if update_fields:
                    update_fields.append('updated_at')
                    asset.save(update_fields=update_fields)

            holding, created = TrackedAssetHolding.objects.get_or_create(
                asset=asset,
                user=user,
                defaults={'quantity': amount}
            )
            if not created and holding.quantity != amount:
                holding.quantity = amount
                holding.save(update_fields=['quantity', 'updated_at'])

        # Zero out holdings for assets no longer present
        user_asset_symbols = set(
            TrackedAssetHolding.objects.filter(user=user)
            .values_list('asset__symbol', flat=True)
        )
        missing_symbols = user_asset_symbols - asset_symbols
        if missing_symbols:
            TrackedAssetHolding.objects.filter(
                user=user,
                asset__symbol__in=missing_symbols
            ).update(quantity=Decimal('0'))

        # Update total quantities for affected assets
        affected_symbols = user_asset_symbols | asset_symbols
        for asset in TrackedAsset.objects.filter(symbol__in=affected_symbols):
            total = (
                TrackedAssetHolding.objects.filter(asset=asset)
                .aggregate(total=Sum('quantity'))['total']
                or Decimal('0')
            )
            if asset.total_quantity != total:
                asset.total_quantity = total
                asset.save(update_fields=['total_quantity', 'updated_at'])
