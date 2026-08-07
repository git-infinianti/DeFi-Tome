from django.contrib import admin
from .models import MembershipPlan, UserMembership, UserProfile

# Register your models here.
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'theme', 'network_mode', 'rpc_endpoint_mode', 'created_at', 'updated_at')
    list_filter = ('theme', 'network_mode', 'rpc_endpoint_mode', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'theme', 'network_mode', 'rpc_endpoint_mode')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('code', 'name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserMembership)
class UserMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'starts_at', 'expires_at', 'updated_at')
    list_filter = ('status', 'plan', 'starts_at', 'expires_at')
    search_fields = ('user__username', 'user__email', 'plan__code', 'plan__name')
    readonly_fields = ('created_at', 'updated_at')
