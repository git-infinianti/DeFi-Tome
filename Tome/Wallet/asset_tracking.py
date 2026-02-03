from decimal import Decimal
from django.db import transaction
from django.db.models import Sum

from .models import TrackedAsset, TrackedAssetHolding


def classify_asset_type(symbol: str) -> str:
    if symbol.endswith('!'):
        return TrackedAsset.ASSET_TYPE_ADMIN
    if symbol.startswith('$'):
        return TrackedAsset.ASSET_TYPE_RESTRICTED
    if symbol.startswith('#'):
        if '/' in symbol:
            return TrackedAsset.ASSET_TYPE_SUB_QUALIFIER
        return TrackedAsset.ASSET_TYPE_QUALIFIER
    if '~' in symbol:
        return TrackedAsset.ASSET_TYPE_MESSAGING
    if '#' in symbol:
        return TrackedAsset.ASSET_TYPE_UNIQUE
    if '/' in symbol:
        return TrackedAsset.ASSET_TYPE_SUB
    return TrackedAsset.ASSET_TYPE_MAIN


def sync_tracked_assets(user, asset_balances: dict) -> None:
    """
    Persist tracked assets and user holdings from a balance dict.

    Args:
        user: Django User
        asset_balances: dict of {symbol: Decimal}
    """
    if user is None:
        return

    asset_symbols = set(asset_balances.keys())

    with transaction.atomic():
        # Track current assets and holdings
        for symbol, amount in asset_balances.items():
            asset_type = classify_asset_type(symbol)
            asset, created = TrackedAsset.objects.get_or_create(
                symbol=symbol,
                defaults={'asset_type': asset_type}
            )
            if not created and asset.asset_type != asset_type:
                asset.asset_type = asset_type
                asset.save(update_fields=['asset_type', 'updated_at'])

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
