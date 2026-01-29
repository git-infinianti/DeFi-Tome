from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import MarketplaceListing, MarketplaceItem

# Create your views here.
@login_required
def marketplace(request):
    """Display all available marketplace listings"""
    listings = MarketplaceListing.objects.all().select_related('item', 'seller').order_by('-listing_date')
    return render(request, 'marketplace/index.html', {'listings': listings})

@login_required
def create_listing(request):
    """Create a new marketplace listing"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price', '').strip()
        quantity = request.POST.get('quantity', '').strip()
        
        # Validate required fields
        if not title or not description or not price or not quantity:
            messages.error(request, 'All fields are required.')
            return render(request, 'marketplace/create_listing.html')
        
        # Validate numeric fields
        try:
            price_decimal = float(price)
            quantity_int = int(quantity)
            
            if price_decimal <= 0:
                messages.error(request, 'Price must be greater than 0.')
                return render(request, 'marketplace/create_listing.html')
            
            if quantity_int <= 0:
                messages.error(request, 'Quantity must be greater than 0.')
                return render(request, 'marketplace/create_listing.html')
        except ValueError:
            messages.error(request, 'Invalid price or quantity format.')
            return render(request, 'marketplace/create_listing.html')
        
        # Create the marketplace item
        item = MarketplaceItem.objects.create(
            title=title,
            description=description,
            quantity=quantity_int,
            individual_price=price_decimal,
            total_price=price_decimal * quantity_int
        )
        
        # Create the marketplace listing
        MarketplaceListing.objects.create(
            item=item,
            seller=request.user,
            price=price_decimal,
            quantity_available=quantity_int
        )
        
        messages.success(request, 'Listing created successfully!')
        return redirect('marketplace')
    
    return render(request, 'marketplace/create_listing.html')
