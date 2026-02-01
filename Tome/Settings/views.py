from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings as django_settings
from django.urls import reverse
from django.http import JsonResponse
from User.models import EmailVerification
from .models import UserProfile
from API.models import APIKey


# Helper function to send verification email
def send_verification_email(request, user):
    """Send email verification link to the user
    
    Note: This function uses get_or_create which means the verification token 
    remains the same across multiple calls for the same user. The token is only 
    created once when the EmailVerification record is first created.
    """
    email_verification, created = EmailVerification.objects.get_or_create(user=user)
    
    # Generate verification link
    verification_url = request.build_absolute_uri(
        reverse('verify_email', kwargs={'token': email_verification.verification_token})
    )
    
    # Send email
    subject = 'Verify Your Email - DeFi Tome'
    message = f"""
    Hello {user.username},
    
    Thank you for registering with DeFi Tome!
    
    Please verify your email address by clicking the link below:
    {verification_url}
    
    If you did not create an account, please ignore this email.
    
    Best regards,
    The DeFi Tome Team
    """
    
    send_mail(
        subject,
        message,
        django_settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


@login_required
def settings(request):
    # Get or create email verification record
    email_verification, created = EmailVerification.objects.get_or_create(user=request.user)
    
    # Get or create user profile for theme preference
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get user's API keys
    api_keys = APIKey.objects.filter(user=request.user, is_active=True).order_by('-created_at')
    
    # Check for newly created API key in session
    new_api_key = request.session.pop('new_api_key', None)
    
    context = {
        'email_verification': email_verification,
        'user_profile': user_profile,
        'api_keys': api_keys,
        'new_api_key': new_api_key,
    }
    return render(request, 'settings/index.html', context)


@login_required
@require_http_methods(["POST"])
def resend_verification_email(request):
    """Resend email verification link"""
    email_verification, created = EmailVerification.objects.get_or_create(user=request.user)
    
    if email_verification.is_verified:
        messages.info(request, 'Your email is already verified.')
    else:
        try:
            send_verification_email(request, request.user)
            messages.success(request, 'Verification email has been resent. Please check your inbox.')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Failed to send verification email to {request.user.email}: {str(e)}')
            messages.error(request, f'Failed to send verification email. Please try again later.')
    
    return redirect('settings')


@login_required
@require_http_methods(["POST"])
def change_theme(request):
    """Change user's theme preference"""
    theme = request.POST.get('theme', 'default')
    
    # Validate theme choice against model choices
    valid_themes = [choice[0] for choice in UserProfile.THEME_CHOICES]
    if theme not in valid_themes:
        messages.error(request, 'Invalid theme selection.')
        return redirect('settings')
    
    # Get or create user profile
    user_profile, created = UserProfile.objects.get_or_create(user=request.user)
    user_profile.theme = theme
    user_profile.save()
    
    messages.success(request, f'Theme changed to {dict(UserProfile.THEME_CHOICES)[theme]}.')
    return redirect('settings')


@login_required
@require_http_methods(["POST"])
def create_api_key(request):
    """Create a new API key for the user"""
    name = request.POST.get('name', '').strip()
    
    if not name:
        messages.error(request, 'Please provide a name for the API key.')
        return redirect('settings')
    
    # Generate a new API key
    api_key_string = APIKey.generate_key()
    key_hash = APIKey.hash_key(api_key_string)
    key_prefix = api_key_string[:8]
    
    # Create the API key record
    api_key = APIKey.objects.create(
        user=request.user,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        is_active=True
    )
    
    # Store the full key in session temporarily to display it once
    request.session['new_api_key'] = api_key_string
    request.session['new_api_key_name'] = name
    
    messages.success(request, f'API key "{name}" created successfully! Make sure to copy it now - you won\'t be able to see it again.')
    return redirect('settings')


@login_required
@require_http_methods(["POST"])
def revoke_api_key(request, key_id):
    """Revoke (deactivate) an API key"""
    try:
        api_key = APIKey.objects.get(id=key_id, user=request.user)
        api_key.is_active = False
        api_key.save()
        messages.success(request, f'API key "{api_key.name}" has been revoked.')
    except APIKey.DoesNotExist:
        messages.error(request, 'API key not found.')
    
    return redirect('settings')


@login_required
@require_http_methods(["POST"])
def delete_api_key(request, key_id):
    """Delete an API key permanently"""
    try:
        api_key = APIKey.objects.get(id=key_id, user=request.user)
        key_name = api_key.name
        api_key.delete()
        messages.success(request, f'API key "{key_name}" has been deleted.')
    except APIKey.DoesNotExist:
        messages.error(request, 'API key not found.')
    
    return redirect('settings')
