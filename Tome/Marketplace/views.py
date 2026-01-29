from django.shortcuts import render
from .models import MarketplaceListing

# Create your views here.
def marketplace(request):
    """Display all available marketplace listings"""
    listings = MarketplaceListing.objects.all().select_related('item', 'seller').order_by('-listing_date')
    return render(request, 'marketplace/index.html', {'listings': listings})
