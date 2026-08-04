from django.contrib import admin
from .models import EmailVerification, EvrmoreAuthenticationAddress

# Register your models here.
admin.site.register(EmailVerification)
admin.site.register(EvrmoreAuthenticationAddress)