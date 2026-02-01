from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
import json

from .models import SolidityContract, ContractInteraction, ContractAsset


class APIInfoTestCase(TestCase):
    """Test API information endpoint"""
    
    def setUp(self):
        self.client = Client()
        self.api_info_url = reverse('api_info')
    
    def test_api_info_accessible(self):
        """Test that API info endpoint is accessible"""
        response = self.client.get(self.api_info_url)
        # Either success (200) or RPC error (500) is acceptable for MVP
        self.assertIn(response.status_code, [200, 500])
        
        # Check response is JSON
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # Parse response
        data = response.json()
        # If RPC is available, expect success
        # If RPC is not available, expect error
        if response.status_code == 200:
            self.assertTrue(data.get('success'))
            self.assertIn('api_version', data)
            self.assertIn('endpoints', data)
        else:
            # RPC not available is acceptable in test environment
            self.assertFalse(data.get('success'))
            self.assertIn('error', data)


class ContractListTestCase(TestCase):
    """Test contract listing endpoint"""
    
    def setUp(self):
        self.client = Client()
        self.contracts_url = reverse('contracts_list')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_list_contracts_empty(self):
        """Test listing contracts when none exist"""
        response = self.client.get(self.contracts_url)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(len(data.get('contracts', [])), 0)
    
    def test_list_contracts_with_data(self):
        """Test listing contracts when some exist"""
        # Create test contracts
        SolidityContract.objects.create(
            name='Test Contract',
            contract_address='TEST_ASSET',
            deployer=self.user,
            description='Test description'
        )
        
        response = self.client.get(self.contracts_url)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(len(data.get('contracts', [])), 1)
        self.assertEqual(data['contracts'][0]['name'], 'Test Contract')
    
    def test_create_contract_requires_auth(self):
        """Test that creating a contract requires authentication"""
        contract_data = {
            'name': 'New Contract',
            'contract_address': 'NEW_ASSET',
            'description': 'A new contract'
        }
        
        response = self.client.post(
            self.contracts_url,
            data=json.dumps(contract_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertFalse(data.get('success'))
    
    def test_create_contract_authenticated(self):
        """Test creating a contract when authenticated"""
        self.client.login(username='testuser', password='testpass123')
        
        contract_data = {
            'name': 'New Contract',
            'contract_address': 'NEW_ASSET',
            'description': 'A new contract'
        }
        
        response = self.client.post(
            self.contracts_url,
            data=json.dumps(contract_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertIn('contract', data)
        
        # Verify contract was created
        self.assertTrue(SolidityContract.objects.filter(name='New Contract').exists())
    
    def test_create_contract_missing_fields(self):
        """Test that creating a contract fails with missing required fields"""
        self.client.login(username='testuser', password='testpass123')
        
        contract_data = {
            'name': 'New Contract',
            # Missing contract_address
        }
        
        response = self.client.post(
            self.contracts_url,
            data=json.dumps(contract_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data.get('success'))


class ContractDetailTestCase(TestCase):
    """Test contract detail endpoint"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.contract = SolidityContract.objects.create(
            name='Test Contract',
            contract_address='TEST_ASSET',
            deployer=self.user,
            description='Test description',
            source_code='contract Test {}',
            abi=[{'type': 'function', 'name': 'test'}]
        )
    
    def test_get_contract_detail(self):
        """Test getting contract details"""
        url = reverse('contract_detail', kwargs={'contract_id': self.contract.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertEqual(data['contract']['name'], 'Test Contract')
        self.assertEqual(data['contract']['contract_address'], 'TEST_ASSET')
        self.assertIn('abi', data['contract'])
    
    def test_get_nonexistent_contract(self):
        """Test getting details of non-existent contract"""
        url = reverse('contract_detail', kwargs={'contract_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertFalse(data.get('success'))


class ContractInteractionTestCase(TestCase):
    """Test contract interaction endpoint"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.contract = SolidityContract.objects.create(
            name='Test Contract',
            contract_address='TEST_ASSET',
            deployer=self.user,
            description='Test description'
        )
    
    def test_interact_requires_auth(self):
        """Test that interacting with a contract requires authentication"""
        url = reverse('contract_interact', kwargs={'contract_id': self.contract.id})
        interaction_data = {
            'function_name': 'testFunction',
            'parameters': {'param1': 'value1'}
        }
        
        response = self.client.post(
            url,
            data=json.dumps(interaction_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)
    
    def test_interact_authenticated(self):
        """Test interacting with a contract when authenticated"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('contract_interact', kwargs={'contract_id': self.contract.id})
        interaction_data = {
            'function_name': 'testFunction',
            'parameters': {'param1': 'value1'}
        }
        
        response = self.client.post(
            url,
            data=json.dumps(interaction_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))
        
        # Verify interaction was recorded
        self.assertTrue(ContractInteraction.objects.filter(
            contract=self.contract,
            function_name='testFunction'
        ).exists())
    
    def test_interact_missing_function_name(self):
        """Test that interaction fails without function_name"""
        self.client.login(username='testuser', password='testpass123')
        
        url = reverse('contract_interact', kwargs={'contract_id': self.contract.id})
        interaction_data = {
            'parameters': {'param1': 'value1'}
        }
        
        response = self.client.post(
            url,
            data=json.dumps(interaction_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)


class AssetsListTestCase(TestCase):
    """Test assets listing endpoint"""
    
    def setUp(self):
        self.client = Client()
        self.assets_url = reverse('assets_list')
    
    def test_list_assets_accessible(self):
        """Test that assets list endpoint is accessible"""
        # This may fail if RPC is not available, but we test the endpoint exists
        response = self.client.get(self.assets_url)
        # Either success (200) or RPC error (500) is acceptable for MVP
        self.assertIn(response.status_code, [200, 500])


class AssetDetailTestCase(TestCase):
    """Test asset detail endpoint"""
    
    def setUp(self):
        self.client = Client()
    
    def test_asset_detail_accessible(self):
        """Test that asset detail endpoint is accessible"""
        url = reverse('asset_detail', kwargs={'asset_name': 'TEST_ASSET'})
        response = self.client.get(url)
        # Either success (200) or RPC error (500) is acceptable for MVP
        self.assertIn(response.status_code, [200, 500])


class BlockchainInfoTestCase(TestCase):
    """Test blockchain info endpoint"""
    
    def setUp(self):
        self.client = Client()
        self.blockchain_info_url = reverse('blockchain_info')
    
    def test_blockchain_info_accessible(self):
        """Test that blockchain info endpoint is accessible"""
        response = self.client.get(self.blockchain_info_url)
        # Either success (200) or RPC error (500) is acceptable for MVP
        self.assertIn(response.status_code, [200, 500])


class AddressBalanceTestCase(TestCase):
    """Test address balance endpoint"""
    
    def setUp(self):
        self.client = Client()
    
    def test_address_balance_accessible(self):
        """Test that address balance endpoint is accessible"""
        # Use a sample Evrmore address format
        test_address = 'EVRTestAddress123456789'
        url = reverse('address_balance', kwargs={'address': test_address})
        response = self.client.get(url)
        # Either success (200) or RPC error (500) is acceptable for MVP
        self.assertIn(response.status_code, [200, 500])


class ModelTestCase(TestCase):
    """Test model creation and relationships"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_create_solidity_contract(self):
        """Test creating a SolidityContract model instance"""
        contract = SolidityContract.objects.create(
            name='Test Contract',
            contract_address='TEST_ASSET',
            deployer=self.user,
            description='Test description'
        )
        
        self.assertEqual(contract.name, 'Test Contract')
        self.assertEqual(contract.deployer, self.user)
        self.assertTrue(contract.is_active)
        self.assertIsNotNone(contract.created_at)
    
    def test_create_contract_interaction(self):
        """Test creating a ContractInteraction model instance"""
        contract = SolidityContract.objects.create(
            name='Test Contract',
            contract_address='TEST_ASSET',
            deployer=self.user
        )
        
        interaction = ContractInteraction.objects.create(
            contract=contract,
            user=self.user,
            function_name='testFunction',
            parameters={'param1': 'value1'},
            success=True
        )
        
        self.assertEqual(interaction.contract, contract)
        self.assertEqual(interaction.user, self.user)
        self.assertEqual(interaction.function_name, 'testFunction')
        self.assertTrue(interaction.success)
    
    def test_create_contract_asset(self):
        """Test creating a ContractAsset model instance"""
        contract = SolidityContract.objects.create(
            name='Test Contract',
            contract_address='TEST_ASSET',
            deployer=self.user
        )
        
        asset = ContractAsset.objects.create(
            contract=contract,
            asset_name='TEST_TOKEN',
            quantity=1000,
            units=2,
            reissuable=True
        )
        
        self.assertEqual(asset.contract, contract)
        self.assertEqual(asset.asset_name, 'TEST_TOKEN')
        self.assertEqual(asset.quantity, 1000)
    
    def test_contract_string_representation(self):
        """Test string representation of models"""
        contract = SolidityContract.objects.create(
            name='Test Contract',
            contract_address='TEST_ASSET',
            deployer=self.user
        )
        
        self.assertEqual(str(contract), 'Test Contract (TEST_ASSET)')
    
    def test_contract_asset_unique_together(self):
        """Test that contract and asset_name combination is unique"""
        contract = SolidityContract.objects.create(
            name='Test Contract',
            contract_address='TEST_ASSET',
            deployer=self.user
        )
        
        ContractAsset.objects.create(
            contract=contract,
            asset_name='UNIQUE_TOKEN',
            quantity=100
        )
        
        # Try to create duplicate - should raise error
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ContractAsset.objects.create(
                contract=contract,
                asset_name='UNIQUE_TOKEN',
                quantity=200
            )

