from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db.models import Q
from decimal import Decimal

# Create your models here.
class UserWallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_wallet')
    name = models.CharField(max_length=256, default='My Wallet')
    entropy = models.CharField(max_length=256)
    passphrase = models.CharField(max_length=256, blank=True)
    evr_liquidity = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    last_balance_update = models.DateTimeField(blank=True, null=True)
    evr_liquidity_mainnet = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    evr_liquidity_testnet = models.DecimalField(max_digits=20, decimal_places=8, default=Decimal('0'))
    last_balance_update_mainnet = models.DateTimeField(blank=True, null=True)
    last_balance_update_testnet = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"UserWallet(name={self.name}, user_id={self.user_id})"

class WalletAddress(models.Model):
    NETWORK_MODE_MAINNET = 'mainnet'
    NETWORK_MODE_TESTNET = 'testnet'
    NETWORK_MODE_CHOICES = [
        (NETWORK_MODE_MAINNET, 'Mainnet'),
        (NETWORK_MODE_TESTNET, 'Testnet'),
    ]

    wallet = models.ForeignKey(UserWallet, on_delete=models.CASCADE, related_name='addresses')
    network_mode = models.CharField(max_length=10, choices=NETWORK_MODE_CHOICES, default=NETWORK_MODE_MAINNET)
    address = models.CharField(max_length=256)
    wif = models.CharField(max_length=256)
    account = models.PositiveIntegerField()
    index = models.PositiveIntegerField()
    is_change = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('wallet', 'network_mode', 'account', 'index', 'is_change')
    
    def __str__(self):
        return f"WalletAddress(address={self.address}, network={self.network_mode}, index={self.index})"


class WalletProfile(models.Model):
    wallet = models.ForeignKey(UserWallet, on_delete=models.CASCADE, related_name='profiles')
    address = models.OneToOneField(WalletAddress, on_delete=models.CASCADE, related_name='wallet_profile')
    network_mode = models.CharField(
        max_length=10,
        choices=WalletAddress.NETWORK_MODE_CHOICES,
        default=WalletAddress.NETWORK_MODE_MAINNET,
    )
    name = models.CharField(max_length=100)
    is_main = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('wallet', 'network_mode'),
                condition=Q(is_main=True),
                name='wallet_one_main_profile_per_network',
            ),
            models.UniqueConstraint(
                fields=('wallet', 'network_mode', 'name'),
                name='wallet_profile_name_unique_per_network',
            ),
        ]

    def clean(self):
        if not self.address_id:
            return

        if self.address.wallet_id != self.wallet_id:
            raise ValidationError('The selected address does not belong to this wallet.')

        if self.address.network_mode != self.network_mode:
            raise ValidationError('The selected address is not on the active network for this profile.')

        if self.address.is_change:
            raise ValidationError('Change addresses cannot be assigned to wallet profiles.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"WalletProfile(name={self.name}, address={self.address.address}, main={self.is_main})"


class TrackedAsset(models.Model):
    NETWORK_MODE_MAINNET = 'mainnet'
    NETWORK_MODE_TESTNET = 'testnet'
    NETWORK_MODE_CHOICES = [
        (NETWORK_MODE_MAINNET, 'Mainnet'),
        (NETWORK_MODE_TESTNET, 'Testnet'),
    ]

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

    symbol = models.CharField(max_length=255)
    network_mode = models.CharField(max_length=10, choices=NETWORK_MODE_CHOICES, default=NETWORK_MODE_MAINNET)
    asset_type = models.CharField(max_length=32, choices=ASSET_TYPE_CHOICES, default=ASSET_TYPE_MAIN)
    total_quantity = models.DecimalField(max_digits=30, decimal_places=8, default=Decimal('0'))
    
    # Asset metadata fields
    ipfs_hash = models.CharField(max_length=255, blank=True, null=True, help_text="IPFS hash for asset metadata")
    has_toll = models.BooleanField(default=False, help_text="Whether asset has transfer toll enabled")
    toll_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'), help_text="Toll percentage for transfers")
    toll_address = models.CharField(max_length=100, blank=True, null=True, help_text="Address receiving toll payments")
    is_reissuable = models.BooleanField(default=True, help_text="Whether asset can be reissued")
    units = models.IntegerField(default=0, help_text="Decimal places for asset divisibility (0-8)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('symbol', 'network_mode'),
                name='tracked_asset_symbol_network_unique',
            ),
        ]

    def __str__(self):
        return f"TrackedAsset(symbol={self.symbol}, network={self.network_mode}, type={self.asset_type})"


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


class SafeTradeCredentials(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='safe_trade_credentials')
    api_key = models.CharField(max_length=255)
    api_secret = models.CharField(max_length=255)
    member_info = models.JSONField(blank=True, null=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SafeTradeCredentials(user_id={self.user_id})"
    
