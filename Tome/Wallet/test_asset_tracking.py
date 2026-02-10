"""
Test asset type classification for Evrmore blockchain assets.
"""
from django.test import TestCase
from .asset_tracking import classify_asset_type
from .models import TrackedAsset


class AssetTypeClassificationTest(TestCase):
    """Test cases for asset type classification"""
    
    def test_main_asset(self):
        """Test main asset classification"""
        result = classify_asset_type('MYTOKEN')
        self.assertEqual(result, TrackedAsset.ASSET_TYPE_MAIN)
    
    def test_sub_asset(self):
        """Test sub-asset classification"""
        result = classify_asset_type('PARENT/CHILD')
        self.assertEqual(result, TrackedAsset.ASSET_TYPE_SUB)
    
    def test_unique_asset(self):
        """Test unique asset classification"""
        result = classify_asset_type('MYTOKEN#123')
        self.assertEqual(result, TrackedAsset.ASSET_TYPE_UNIQUE)
    
    def test_messaging_channel(self):
        """Test messaging channel classification"""
        result = classify_asset_type('MYCHANNEL~')
        self.assertEqual(result, TrackedAsset.ASSET_TYPE_MESSAGING)
    
    def test_qualifier(self):
        """Test qualifier classification"""
        result = classify_asset_type('#QUALIFIER')
        self.assertEqual(result, TrackedAsset.ASSET_TYPE_QUALIFIER)
    
    def test_sub_qualifier(self):
        """Test sub-qualifier classification"""
        result = classify_asset_type('#QUALIFIER/SUB')
        self.assertEqual(result, TrackedAsset.ASSET_TYPE_SUB_QUALIFIER)
    
    def test_restricted_asset(self):
        """Test restricted asset classification"""
        result = classify_asset_type('$RESTRICTED')
        self.assertEqual(result, TrackedAsset.ASSET_TYPE_RESTRICTED)
    
    def test_admin_token(self):
        """Test admin token classification"""
        result = classify_asset_type('ADMIN!')
        self.assertEqual(result, TrackedAsset.ASSET_TYPE_ADMIN)
    
    def test_nft_asset(self):
        """Test NFT asset classification with metadata"""
        nft_data = {
            'amount': 1,
            'reissuable': False,
            'has_ipfs': True,
            'ipfs_hash': 'QmXxxx...'
        }
        result = classify_asset_type('MYNFT', nft_data)
        self.assertEqual(result, TrackedAsset.ASSET_TYPE_NFT)
    
    def test_vault_asset(self):
        """Test vault asset classification with toll enabled"""
        vault_data = {
            'has_toll': True,
            'toll_percentage': 5.0,
            'toll_address': 'EVRxxxxxxxxxx'
        }
        result = classify_asset_type('MYVAULT', vault_data)
        self.assertEqual(result, TrackedAsset.ASSET_TYPE_VAULT)
    
    def test_regular_asset_with_metadata(self):
        """Test regular asset doesn't become NFT/vault without right metadata"""
        regular_data = {
            'amount': 1000,
            'reissuable': True,
            'has_ipfs': False
        }
        result = classify_asset_type('REGULARTOKEN', regular_data)
        self.assertEqual(result, TrackedAsset.ASSET_TYPE_MAIN)
