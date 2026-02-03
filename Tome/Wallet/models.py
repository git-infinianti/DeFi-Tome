from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

# Create your models here.
class UserWallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_wallet')
    name = models.CharField(max_length=256, default='My Wallet')
    entropy = models.CharField(max_length=256)
    passphrase = models.CharField(max_length=256, blank=True)
    evr_liquidity = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    last_balance_update = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"UserWallet(name={self.name}, user_id={self.user_id})"

class WalletAddress(models.Model):
    wallet = models.ForeignKey(UserWallet, on_delete=models.CASCADE, related_name='addresses')
    address = models.CharField(max_length=256)
    wif = models.CharField(max_length=256)
    account = models.PositiveIntegerField()
    index = models.PositiveIntegerField()
    is_change = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"WalletAddress(address={self.address}, index={self.index})"


class TrackedAsset(models.Model):
    ASSET_TYPE_MAIN = 'main'
    ASSET_TYPE_SUB = 'sub'
    ASSET_TYPE_UNIQUE = 'unique'
    ASSET_TYPE_MESSAGING = 'messaging_channel'
    ASSET_TYPE_QUALIFIER = 'qualifier'
    ASSET_TYPE_SUB_QUALIFIER = 'sub_qualifier'
    ASSET_TYPE_RESTRICTED = 'restricted'
    ASSET_TYPE_ADMIN = 'administrator'

    ASSET_TYPE_CHOICES = (
        (ASSET_TYPE_MAIN, 'Main'),
        (ASSET_TYPE_SUB, 'Sub'),
        (ASSET_TYPE_UNIQUE, 'Unique'),
        (ASSET_TYPE_MESSAGING, 'Messaging Channel'),
        (ASSET_TYPE_QUALIFIER, 'Qualifier'),
        (ASSET_TYPE_SUB_QUALIFIER, 'Sub Qualifier'),
        (ASSET_TYPE_RESTRICTED, 'Restricted'),
        (ASSET_TYPE_ADMIN, 'Administrator'),
    )

    symbol = models.CharField(max_length=255, unique=True)
    asset_type = models.CharField(max_length=32, choices=ASSET_TYPE_CHOICES, default=ASSET_TYPE_MAIN)
    total_quantity = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal('0'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"TrackedAsset(symbol={self.symbol}, type={self.asset_type})"


class TrackedAssetHolding(models.Model):
    asset = models.ForeignKey(TrackedAsset, on_delete=models.CASCADE, related_name='holdings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='asset_holdings')
    quantity = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal('0'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('asset', 'user')

    def __str__(self):
        return f"TrackedAssetHolding(asset={self.asset.symbol}, user_id={self.user_id}, qty={self.quantity})"