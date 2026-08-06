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
