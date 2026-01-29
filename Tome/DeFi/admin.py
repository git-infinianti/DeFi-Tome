from django.contrib import admin
from .models import TestnetConfig, LiquidityPool, LiquidityPosition, SwapTransaction

# Register your models here.
admin.site.register(TestnetConfig)
admin.site.register(LiquidityPool)
admin.site.register(LiquidityPosition)
admin.site.register(SwapTransaction)
