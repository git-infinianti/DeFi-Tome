from django.contrib.auth.models import Group
from django.utils import timezone

FEATURE_MARKET_MANAGEMENT = 'market_management'
FEATURE_PREMIUM_SWAP_TOOLS = 'premium_swap_tools'

MARKET_MANAGERS_GROUP = 'market_managers'


def user_has_feature_access(user, feature_code):
    """Return True when a user is authorized for a feature gate."""
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    # Support Django permissions in addition to membership checks.
    if feature_code == FEATURE_MARKET_MANAGEMENT:
        if user.has_perm('Listings.add_tradingpair') or user.has_perm('Listings.change_tradingpair'):
            return True
        if user.groups.filter(name=MARKET_MANAGERS_GROUP).exists():
            return True

    membership = getattr(user, 'membership', None)
    if not membership:
        return False

    if membership.status != 'active':
        return False

    now = timezone.now()
    if membership.starts_at and membership.starts_at > now:
        return False
    if membership.expires_at and membership.expires_at <= now:
        return False

    if not membership.plan or not membership.plan.is_active:
        return False

    feature_codes = membership.plan.feature_codes or []
    return feature_code in feature_codes


def ensure_access_scaffold_groups():
    """Create baseline groups used by feature access checks."""
    Group.objects.get_or_create(name=MARKET_MANAGERS_GROUP)
