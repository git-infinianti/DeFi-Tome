from django.db import models

# Create your models here.
class ExplorerAsset(models.Model):
    symbol = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.symbol

class ExplorerAssetHolding(models.Model):
    asset = models.ForeignKey(ExplorerAsset, on_delete=models.CASCADE, related_name='holdings')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='explorer_asset_holdings')
    quantity = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('asset', 'user')

    def __str__(self):
        return f"{self.user.username} holds {self.quantity} of {self.asset.symbol}"

class ExplorerAssetTransaction(models.Model):
    asset = models.ForeignKey(ExplorerAsset, on_delete=models.CASCADE, related_name='transactions')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='asset_transactions')
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    transaction_type = models.CharField(max_length=50)  # e.g., 'buy', 'sell', 'transfer'
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} of {self.asset.symbol} by {self.user.username}"