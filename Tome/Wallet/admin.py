from django.contrib import admin
from .models import UserWallet, TrackedAsset, TrackedAssetHolding, SafeTradeCredentials

# Register your models here.
admin.site.register(UserWallet)
admin.site.register(TrackedAsset)
admin.site.register(TrackedAssetHolding)
admin.site.register(SafeTradeCredentials)
