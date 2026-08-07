from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class UserProfile(models.Model):
    THEME_CHOICES = [
        ('default', 'Default (Dark)'),
        ('light', 'Light'),
        ('dark', 'Dark'),
    ]
    NETWORK_MODE_CHOICES = [
        ('testnet', 'Testnet'),
        ('mainnet', 'Mainnet'),
    ]
    RPC_ENDPOINT_MODE_CHOICES = [
        ('public', 'Public RPC'),
        ('local', 'Local Node RPC'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    theme = models.CharField(max_length=20, choices=THEME_CHOICES, default='default')
    network_mode = models.CharField(max_length=10, choices=NETWORK_MODE_CHOICES, default='testnet')
    rpc_endpoint_mode = models.CharField(max_length=10, choices=RPC_ENDPOINT_MODE_CHOICES, default='public')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "User Profiles"
    
    def __str__(self):
        return (
            f"UserProfile(user={self.user.username}, "
            f"theme={self.theme}, network_mode={self.network_mode}, "
            f"rpc_endpoint_mode={self.rpc_endpoint_mode})"
        )


class MembershipPlan(models.Model):
    """Membership plan scaffold with feature codes for gated functionality."""
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    feature_codes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"MembershipPlan(code={self.code}, active={self.is_active})"


class UserMembership(models.Model):
    """Maps a user to a membership plan used for feature access checks."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='membership')
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name='memberships')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"UserMembership(user={self.user.username}, plan={self.plan.code}, status={self.status})"
