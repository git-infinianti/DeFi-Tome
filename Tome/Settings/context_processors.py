from .models import UserProfile


def theme_context(request):
    """Add user's theme preference to all template contexts"""
    if request.user.is_authenticated:
        # Use get_or_create to safely handle concurrent requests
        user_profile, created = UserProfile.objects.get_or_create(user=request.user)
        return {'user_theme': user_profile.theme}
    return {'user_theme': 'default'}
