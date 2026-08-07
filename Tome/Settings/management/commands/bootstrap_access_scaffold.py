from django.core.management.base import BaseCommand

from Settings.access import (
    FEATURE_MARKET_MANAGEMENT,
    FEATURE_PREMIUM_SWAP_TOOLS,
    MARKET_MANAGERS_GROUP,
    ensure_access_scaffold_groups,
)
from Settings.models import MembershipPlan


class Command(BaseCommand):
    help = 'Create default membership plans and authorization groups for feature-gated access.'

    def handle(self, *args, **options):
        ensure_access_scaffold_groups()

        defaults = [
            {
                'code': 'free',
                'name': 'Free',
                'description': 'Default tier with basic app access.',
                'feature_codes': [],
            },
            {
                'code': 'pro',
                'name': 'Pro',
                'description': 'Adds advanced market and swap tooling.',
                'feature_codes': [
                    FEATURE_MARKET_MANAGEMENT,
                    FEATURE_PREMIUM_SWAP_TOOLS,
                ],
            },
            {
                'code': 'enterprise',
                'name': 'Enterprise',
                'description': 'Full access tier for teams and operators.',
                'feature_codes': [
                    FEATURE_MARKET_MANAGEMENT,
                    FEATURE_PREMIUM_SWAP_TOOLS,
                ],
            },
        ]

        for plan in defaults:
            MembershipPlan.objects.update_or_create(
                code=plan['code'],
                defaults={
                    'name': plan['name'],
                    'description': plan['description'],
                    'feature_codes': plan['feature_codes'],
                    'is_active': True,
                },
            )

        self.stdout.write(self.style.SUCCESS('Access scaffold initialized.'))
        self.stdout.write(
            f"Group available: {MARKET_MANAGERS_GROUP} (assign users for market management access)."
        )
