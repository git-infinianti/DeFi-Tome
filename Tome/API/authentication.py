"""
API Key Authentication utilities for DeFi Tome API
"""
from django.http import JsonResponse
from django.utils import timezone
from functools import wraps
from .models import APIKey


def get_api_key_from_request(request):
    """
    Extract API key from request headers.
    
    Supports two header formats:
    - Authorization: Bearer <api_key>
    - X-API-Key: <api_key>
    
    Args:
        request: Django request object
        
    Returns:
        API key string or None
    """
    # Check Authorization header
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]  # Remove 'Bearer ' prefix
    
    # Check X-API-Key header
    api_key = request.headers.get('X-API-Key', '')
    if api_key:
        return api_key
    
    return None


def authenticate_api_key(api_key_string):
    """
    Authenticate an API key and return the associated user.
    
    Args:
        api_key_string: The API key to authenticate
        
    Returns:
        User object if valid, None otherwise
    """
    if not api_key_string:
        return None
    
    # Hash the provided key
    key_hash = APIKey.hash_key(api_key_string)
    
    try:
        # Look up the API key
        api_key = APIKey.objects.select_related('user').get(
            key_hash=key_hash,
            is_active=True
        )
        
        # Update last_used timestamp
        api_key.last_used = timezone.now()
        api_key.save(update_fields=['last_used'])
        
        return api_key.user
    except APIKey.DoesNotExist:
        return None


def api_key_required(view_func):
    """
    Decorator to require API key authentication for API endpoints.
    
    Usage:
        @api_key_required
        def my_api_view(request):
            # request.user will be set to the authenticated user
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Get API key from request
        api_key_string = get_api_key_from_request(request)
        
        # Authenticate
        user = authenticate_api_key(api_key_string)
        
        if not user:
            return JsonResponse({
                'success': False,
                'error': 'Invalid or missing API key',
                'message': 'Please provide a valid API key in the Authorization header (Bearer <key>) or X-API-Key header'
            }, status=401)
        
        # Set the user on the request
        request.user = user
        
        # Call the original view
        return view_func(request, *args, **kwargs)
    
    return wrapper
