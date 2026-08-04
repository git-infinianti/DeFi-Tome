from django.db import models
from django.contrib.auth.models import User
import uuid

# Create your models here.
class EmailVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification')
    is_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"EmailVerification(user={self.user.username}, verified={self.is_verified})"


class EvrmoreAuthenticationAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='evrmore_authentication_addresses')
    address = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_authenticated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"EvrmoreAuthenticationAddress(address={self.address}, user={self.user.username})"