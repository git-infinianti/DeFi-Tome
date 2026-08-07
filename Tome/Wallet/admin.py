from django.contrib import admin
from .models import UserWallet, WalletProfile, TrackedAsset, TrackedAssetHolding, SafeTradeCredentials

# Register your models here.
admin.site.register(UserWallet)
admin.site.register(WalletProfile)


@admin.register(TrackedAsset)
class TrackedAssetAdmin(admin.ModelAdmin):
	list_display = ('symbol', 'network_mode', 'asset_type', 'units', 'total_quantity', 'updated_at')
	list_filter = ('network_mode', 'asset_type')
	search_fields = ('symbol',)


admin.site.register(TrackedAssetHolding)
admin.site.register(SafeTradeCredentials)
