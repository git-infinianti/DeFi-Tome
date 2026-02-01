# NFT Feature - Quick Reference Guide

## For Developers

### Testing NFT Creation

1. **Navigate to create listing**: http://localhost:8000/listings/create/
2. **Fill in standard fields**:
   - Title: "My NFT Artwork"
   - Description: "A unique digital artwork"
   - Token Offered: Select from available tokens
   - Preferred Token: EVR (or other)
   - Price: 100.50
   - Expiry: 7 days

3. **Enable NFT**:
   - Check "Create as NFT (1 of 1)" checkbox
   - IPFS CID field appears
   - Enter optional IPFS CID (e.g., `QmXxxxxxxxxxxx`)

4. **Submit**:
   - Form validates
   - Backend creates ListingItem with is_nft=True
   - Backend creates NFT record
   - User redirected to listings

### Testing NFT Display

1. **View listings**: http://localhost:8000/listings/
   - NFT listings show purple badge "🎨 NFT (1 of 1)"

2. **View detail**: Click "View Details" on NFT listing
   - Shows NFT banner
   - Shows IPFS image (if CID provided)
   - Shows NFT metadata section
   - Shows token ID and IPFS CID

### API/View Parameters

**create_listing POST**:
```python
{
    'title': str,
    'description': str,
    'price': str,  # Decimal string
    'token_offered': str,  # Token symbol
    'preferred_token': str,  # Token symbol
    'counterparty': str,  # Optional username
    'expiry_days': str,  # 1-365
    'is_nft': 'true'|'false',  # NEW
    'nft_image_ipfs_cid': str,  # NEW, optional
}
```

**listing_detail context**:
```python
{
    'listing': Listing object,
    'nft': NFT object (or None),
    'nft_image_url': str (IPFS gateway URL or None),
}
```

### Model Usage Examples

**Creating an NFT in code**:
```python
from Listings.models import ListingItem, NFT
from decimal import Decimal
import uuid

# Create listing item
item = ListingItem.objects.create(
    title='Digital Art',
    description='Unique artwork',
    quantity=Decimal('1'),
    individual_price=Decimal('100.00'),
    total_price=Decimal('100.00'),
    is_nft=True,
    nft_image_ipfs_cid='QmXxxxxxxxxxxx'
)

# Create NFT record
nft = NFT.objects.create(
    listing_item=item,
    owner=user,
    creator=user,
    image_ipfs_cid='QmXxxxxxxxxxxx',
    token_id=f'nft-{uuid.uuid4()}',
    is_listed=True
)
```

**Accessing NFT from ListingItem**:
```python
listing_item = ListingItem.objects.get(id=1)

if listing_item.is_nft:
    nft = listing_item.nft  # OneToOne relationship
    image_url = nft.get_ipfs_url()
    print(f"NFT ID: {nft.token_id}")
    print(f"IPFS: {image_url}")
```

**Querying NFTs**:
```python
from Listings.models import NFT

# All NFTs
all_nfts = NFT.objects.all()

# NFTs by owner
user_nfts = NFT.objects.filter(owner=user)

# Listed NFTs
listed_nfts = NFT.objects.filter(is_listed=True)

# NFTs by creator
created_nfts = NFT.objects.filter(creator=user)
```

### Frontend Integration

**Show NFT badge in template**:
```django
{% if listing.item.is_nft %}
    <span class="nft-badge">🎨 NFT (1 of 1)</span>
{% endif %}
```

**Display IPFS image**:
```django
{% if nft_image_url %}
    <img src="{{ nft_image_url }}" alt="{{ listing.item.title }}">
{% endif %}
```

**Show NFT metadata**:
```django
{% if nft and nft.image_ipfs_cid %}
    <div class="nft-info-box">
        <div class="nft-info-label">NFT Token ID</div>
        <div class="nft-info-value">{{ nft.token_id }}</div>
        
        <div class="nft-info-label">Image IPFS CID</div>
        <div class="nft-info-value">{{ nft.image_ipfs_cid }}</div>
    </div>
{% endif %}
```

### Common IPFS CIDs for Testing

Example valid CIDs you can use for testing:

- **CIDv0**: `QmXxxxxxxxxxxx` (example format, base58 encoded)
- **CIDv1**: `bafyxxxxxxxxxx` (example format, base32 encoded)

To get real IPFS CIDs, you can:
1. Upload to IPFS directly via https://ipfs.io/
2. Use IPFS CLI: `ipfs add filename`
3. Use services like Pinata or NFT.Storage

### Validation Rules

**Frontend**:
- IPFS CID: max 100 characters
- Dynamic show/hide of NFT fields

**Backend**:
- NFT quantity: must be exactly 1
- IPFS CID: max 100 characters
- ListingItem.is_nft enforced as boolean

### Database Schema

**ListingItem (updated)**:
```sql
ALTER TABLE listings_listingitem ADD COLUMN is_nft BOOLEAN DEFAULT FALSE;
ALTER TABLE listings_listingitem ADD COLUMN nft_image_ipfs_cid VARCHAR(100) NULL;
```

**NFT (new)**:
```sql
CREATE TABLE listings_nft (
    id INT PRIMARY KEY AUTO_INCREMENT,
    listing_item_id INT UNIQUE NOT NULL,
    owner_id INT NOT NULL,
    creator_id INT NOT NULL,
    image_ipfs_cid VARCHAR(100) NOT NULL,
    token_id VARCHAR(100) UNIQUE NOT NULL,
    contract_address VARCHAR(100) NULL,
    tx_hash VARCHAR(100) NULL,
    is_listed BOOLEAN DEFAULT FALSE,
    created_at DATETIME AUTO_NOW_ADD,
    updated_at DATETIME AUTO_NOW,
    FOREIGN KEY (listing_item_id) REFERENCES listings_listingitem(id),
    FOREIGN KEY (owner_id) REFERENCES auth_user(id),
    FOREIGN KEY (creator_id) REFERENCES auth_user(id)
);
```

### Admin Interface

NFT model is registered in Django admin:
- Location: http://localhost:8000/admin/listings/nft/
- Can view/edit NFT records
- Can filter by owner, creator, is_listed
- Can see associated ListingItem

### Debugging Tips

**Check if NFT was created**:
```python
from Listings.models import NFT, ListingItem

item = ListingItem.objects.get(title='My NFT')
print(f"Is NFT: {item.is_nft}")
print(f"IPFS CID: {item.nft_image_ipfs_cid}")

nft = item.nft
print(f"NFT Token ID: {nft.token_id}")
print(f"IPFS URL: {nft.get_ipfs_url()}")
```

**Check IPFS image loads**:
- Open IPFS gateway URL in browser
- Should display image if CID is valid
- Example: https://ipfs.io/ipfs/QmXxxxxxxxxxxx

**Check form submission**:
- Open browser DevTools
- Go to Network tab
- Create listing and check POST request
- Look for `is_nft` and `nft_image_ipfs_cid` in form data

### Performance Considerations

- NFT queryset uses `select_related('listing_item')` where applicable
- OneToOne relationship provides efficient lookups
- IPFS gateway queries are client-side (no backend overhead)
- Consider caching for frequently accessed NFTs

### Future Improvements

- [ ] Batch create NFTs
- [ ] NFT metadata JSON schema
- [ ] Royalty tracking
- [ ] On-chain minting integration
- [ ] NFT transfer/ownership history
- [ ] Collection/series support
- [ ] Rarity scoring
- [ ] Advanced search/filtering

---

## Troubleshooting

**Q: NFT checkbox doesn't show IPFS field?**
- A: Check browser console for JS errors
- A: Verify form-group ID is `nft-image-group`
- A: Check CSS isn't hiding the element

**Q: IPFS image doesn't load?**
- A: Verify CID format (QmXxx or bafyxxx)
- A: Try using gateway directly in browser
- A: Some IPFS nodes may be slower, try again

**Q: NFT record not created?**
- A: Check backend validation errors in messages
- A: Verify quantity equals 1 for NFT
- A: Check database migrations applied

**Q: Price shows wrong token?**
- A: Verify `listing.preferred_token` in template
- A: Not hardcoded to 'TOME' anymore

**Q: NFT badge not showing?**
- A: Verify `listing.item.is_nft` is True in database
- A: Check template conditional syntax
- A: Clear browser cache

---

## Support Channels

For issues or questions:
1. Check browser console for JavaScript errors
2. Check Django logs for backend errors
3. Verify database migrations with: `python manage.py migrate --check`
4. Test in admin interface to rule out frontend issues
