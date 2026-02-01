from django.db import models

# Create your models here.
''' 
The Listings app is where all the logic related to the peer-to-peer DEX will reside. This includes models for items, categories, and transactions.
The listings will be mainly focused on listing other coins to buy/sell/trade using DeFi Tome's wallet system. As well as NFTs.
'''
# Create ListingItem model
class ListingItem(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=20, decimal_places=8, default=1)
    individual_price = models.DecimalField(max_digits=20, decimal_places=8)
    total_price = models.DecimalField(max_digits=20, decimal_places=8)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # NFT fields
    is_nft = models.BooleanField(default=False)
    nft_image_ipfs_cid = models.CharField(max_length=100, blank=True, null=True, help_text="IPFS CID for NFT image")
    
    def __str__(self):
        return self.title

# Create ListingCategory model
class ListingCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

# Create relationship between ListingItem and ListingCategory
class ItemCategory(models.Model):
    item = models.ForeignKey(ListingItem, on_delete=models.CASCADE, related_name='categories')
    category = models.ForeignKey(ListingCategory, on_delete=models.CASCADE, related_name='items')
    
    def __str__(self):
        return f"{self.item.title} in {self.category.name}"
    
# Create ListingTransaction model
class ListingTransaction(models.Model):
    item = models.ForeignKey(ListingItem, on_delete=models.CASCADE, related_name='transactions')
    buyer = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='purchases')
    seller = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='sales')
    quantity = models.DecimalField(max_digits=20, decimal_places=8, default=1)
    individual_price = models.DecimalField(max_digits=20, decimal_places=8)
    total_price = models.DecimalField(max_digits=20, decimal_places=8)
    transaction_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Transaction of {self.item.title} by {self.buyer}"

# Create ListingReview model
class ListingReview(models.Model):
    item = models.ForeignKey(ListingItem, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Review of {self.item.title} by {self.user.username}"

# Create Listing model
class Listing(models.Model):
    item = models.ForeignKey(ListingItem, on_delete=models.CASCADE, related_name='listings')
    seller = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='listings')
    price = models.DecimalField(max_digits=20, decimal_places=8)
    quantity_available = models.DecimalField(max_digits=20, decimal_places=8, default=1)
    listing_date = models.DateTimeField(auto_now_add=True)
    
    # P2P swap fields - MANDATORY
    token_offered = models.CharField(max_length=10)
    preferred_token = models.CharField(max_length=10)
    
    def __str__(self):
        return f"Listing of {self.item.title} by {self.seller.username}"

class ListingOrder(models.Model):
    transaction = models.ForeignKey(ListingTransaction, on_delete=models.CASCADE, related_name='orders')
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='Pending')
    
    def __str__(self):
        return f"Order for {self.transaction.item.title} - Status: {self.status}"

# Order Book DEX Models
class TradingPair(models.Model):
    """Trading pair for order book (e.g., BTC/USDT)"""
    base_token = models.CharField(max_length=10)  # e.g., BTC
    quote_token = models.CharField(max_length=10)  # e.g., USDT
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_pairs')
    created_at = models.DateTimeField(auto_now_add=True)
    last_price = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    high_24h = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    low_24h = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    volume_24h = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    amount_24h = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    price_change_24h = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # percentage
    
    class Meta:
        unique_together = ['base_token', 'quote_token']
    
    def __str__(self):
        return f"{self.base_token}/{self.quote_token}"
    
    def get_24h_stats(self):
        """Calculate 24h statistics from order executions"""
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Sum, Min, Max, Count
        
        since = timezone.now() - timedelta(hours=24)
        executions = self.executions.filter(created_at__gte=since)
        
        if executions.exists():
            stats = executions.aggregate(
                high=Max('price'),
                low=Min('price'),
                volume=Sum('quantity'),
                amount=Count('id')
            )
            last_execution = self.executions.order_by('-created_at').first()
            first_price = executions.order_by('created_at').first().price if executions.exists() else self.last_price
            
            if last_execution:
                self.last_price = last_execution.price
                if first_price and first_price > 0:
                    self.price_change_24h = ((self.last_price - first_price) / first_price) * 100
            
            self.high_24h = stats['high'] or 0
            self.low_24h = stats['low'] or 0
            self.volume_24h = stats['volume'] or 0
            self.amount_24h = stats['amount'] or 0
            self.save()
        
        return {
            'last_price': self.last_price,
            'price_change_24h': self.price_change_24h,
            'high_24h': self.high_24h,
            'low_24h': self.low_24h,
            'volume_24h': self.volume_24h,
            'amount_24h': self.amount_24h,
        }

class LimitOrder(models.Model):
    """Limit order in the order book"""
    ORDER_SIDE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partially Filled'),
        ('filled', 'Filled'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='limit_orders')
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE, related_name='limit_orders', db_index=True)
    side = models.CharField(max_length=4, choices=ORDER_SIDE_CHOICES, db_index=True)
    price = models.DecimalField(max_digits=20, decimal_places=8, db_index=True)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    filled_quantity = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.side.upper()} {self.quantity} {self.trading_pair.base_token} @ {self.price}"
    
    @property
    def remaining_quantity(self):
        return self.quantity - self.filled_quantity

class MarketOrder(models.Model):
    """Market order for instant execution"""
    ORDER_SIDE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
    ]
    STATUS_CHOICES = [
        ('executed', 'Executed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='market_orders')
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE, related_name='market_orders')
    side = models.CharField(max_length=4, choices=ORDER_SIDE_CHOICES)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    executed_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='executed')
    tx_hash = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Market {self.side.upper()} {self.quantity} {self.trading_pair.base_token}"

class StopLossOrder(models.Model):
    """Stop-loss order that triggers when price reaches a threshold"""
    ORDER_SIDE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('triggered', 'Triggered'),
        ('executed', 'Executed'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='stop_loss_orders')
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE, related_name='stop_loss_orders')
    side = models.CharField(max_length=4, choices=ORDER_SIDE_CHOICES)
    trigger_price = models.DecimalField(max_digits=20, decimal_places=8)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    executed_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    tx_hash = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    triggered_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Stop-Loss {self.side.upper()} {self.quantity} {self.trading_pair.base_token} @ {self.trigger_price}"

class OrderExecution(models.Model):
    """Record of an executed order (trade)"""
    trading_pair = models.ForeignKey(TradingPair, on_delete=models.CASCADE, related_name='executions', db_index=True)
    buyer = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='buy_executions', db_index=True)
    seller = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='sell_executions', db_index=True)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    buyer_order = models.ForeignKey(LimitOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='buy_executions')
    seller_order = models.ForeignKey(LimitOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='sell_executions')
    tx_hash = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    def __str__(self):
        return f"Trade: {self.quantity} {self.trading_pair.base_token} @ {self.price}"

class BalanceLock(models.Model):
    """
    Tracks EVR balance locks (reservations) when users place buy orders.
    
    When a user places a buy order, the EVR amount is locked/reserved.
    When the order is filled, cancelled, or expires, the lock is released or consumed.
    """
    STATUS_CHOICES = [
        ('locked', 'Locked'),
        ('released', 'Released'),
        ('consumed', 'Consumed'),
    ]
    
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='balance_locks', db_index=True)
    amount = models.DecimalField(max_digits=20, decimal_places=8, db_index=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='locked', db_index=True)
    
    # Reference to the order that triggered the lock
    limit_order = models.ForeignKey(LimitOrder, on_delete=models.CASCADE, related_name='balance_lock', null=True, blank=True)
    market_order = models.ForeignKey(MarketOrder, on_delete=models.CASCADE, related_name='balance_lock', null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    released_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"BalanceLock({self.user.username}, {self.amount} EVR, {self.status})"
    
    def get_total_locked(user):
        """Get total amount of EVR locked for a user"""
        from django.db.models import Sum
        total = BalanceLock.objects.filter(
            user=user,
            status='locked'
        ).aggregate(total=Sum('amount'))['total']
        return total or 0


class NFT(models.Model):
    """
    NFT model for tracking 1 of 1 unique digital assets.
    Each NFT is associated with a ListingItem that has is_nft=True and quantity=1.
    """
    listing_item = models.OneToOneField(ListingItem, on_delete=models.CASCADE, related_name='nft')
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='owned_nfts')
    creator = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='created_nfts')
    
    # IPFS image CID
    image_ipfs_cid = models.CharField(max_length=100, help_text="IPFS CID for NFT image")
    
    # Metadata
    token_id = models.CharField(max_length=100, unique=True, db_index=True, help_text="Unique token ID for the NFT")
    contract_address = models.CharField(max_length=100, blank=True, null=True, help_text="Blockchain contract address if minted on-chain")
    tx_hash = models.CharField(max_length=100, blank=True, null=True, help_text="Transaction hash for on-chain minting")
    
    # Status
    is_listed = models.BooleanField(default=False, help_text="Whether this NFT is currently listed for sale")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"NFT: {self.listing_item.title} (Owner: {self.owner.username})"
    
    def get_ipfs_url(self):
        """Get IPFS gateway URL for the image"""
        if self.image_ipfs_cid:
            return f"https://ipfs.io/ipfs/{self.image_ipfs_cid}"
        return None