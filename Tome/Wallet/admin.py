from django.contrib import admin
from .models import UserWallet, TrackedAsset, TrackedAssetHolding

# Register your models here.
admin.site.register(UserWallet)
admin.site.register(TrackedAsset)
admin.site.register(TrackedAssetHolding)
