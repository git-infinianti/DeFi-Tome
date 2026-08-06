from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from unittest.mock import MagicMock, patch

from .models import UserProfile
from Tome import rpc_client


class SettingsNetworkModeTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='network-user',
			email='network@example.com',
			password='safe-password-123',
		)
		self.client.login(username='network-user', password='safe-password-123')

	def test_user_profile_defaults_to_testnet(self):
		self.client.get(reverse('settings'))
		profile = UserProfile.objects.get(user=self.user)
		self.assertEqual(profile.network_mode, 'testnet')
		self.assertEqual(profile.rpc_endpoint_mode, 'public')

	def test_change_network_mode_to_mainnet(self):
		response = self.client.post(
			reverse('change_network_mode'),
			{'network_mode': 'mainnet'},
			follow=True,
		)

		self.assertEqual(response.status_code, 200)
		profile = UserProfile.objects.get(user=self.user)
		self.assertEqual(profile.network_mode, 'mainnet')

	def test_invalid_network_mode_is_rejected(self):
		UserProfile.objects.create(user=self.user, network_mode='testnet')

		response = self.client.post(
			reverse('change_network_mode'),
			{'network_mode': 'invalid-network'},
			follow=True,
		)

		self.assertEqual(response.status_code, 200)
		profile = UserProfile.objects.get(user=self.user)
		self.assertEqual(profile.network_mode, 'testnet')

	def test_change_rpc_endpoint_mode_to_local(self):
		response = self.client.post(
			reverse('change_rpc_endpoint_mode'),
			{'rpc_endpoint_mode': 'local'},
			follow=True,
		)

		self.assertEqual(response.status_code, 200)
		profile = UserProfile.objects.get(user=self.user)
		self.assertEqual(profile.rpc_endpoint_mode, 'local')

	def test_invalid_rpc_endpoint_mode_is_rejected(self):
		UserProfile.objects.create(user=self.user, rpc_endpoint_mode='public')

		response = self.client.post(
			reverse('change_rpc_endpoint_mode'),
			{'rpc_endpoint_mode': 'bad-choice'},
			follow=True,
		)

		self.assertEqual(response.status_code, 200)
		profile = UserProfile.objects.get(user=self.user)
		self.assertEqual(profile.rpc_endpoint_mode, 'public')


class RoutedRpcClientTests(TestCase):
	def tearDown(self):
		rpc_client.clear_active_network_mode()
		rpc_client.clear_active_rpc_endpoint_mode()

	def test_normalize_network_mode_defaults_to_testnet(self):
		self.assertEqual(rpc_client.normalize_network_mode(None), 'testnet')
		self.assertEqual(rpc_client.normalize_network_mode('invalid'), 'testnet')
		self.assertEqual(rpc_client.normalize_network_mode('mainnet'), 'mainnet')

	def test_normalize_rpc_endpoint_mode_defaults_to_public(self):
		self.assertEqual(rpc_client.normalize_rpc_endpoint_mode(None), 'public')
		self.assertEqual(rpc_client.normalize_rpc_endpoint_mode('invalid'), 'public')
		self.assertEqual(rpc_client.normalize_rpc_endpoint_mode('local'), 'local')

	@patch('Tome.rpc_client.RoutedEvrmoreClient._get_public_client')
	@patch('Tome.rpc_client.RoutedEvrmoreClient._get_local_client')
	def test_local_failure_falls_back_to_public(self, mock_local_client, mock_public_client):
		local_client = MagicMock()
		public_client = MagicMock()

		local_client.getblockchaininfo.side_effect = Exception('local node unavailable')
		public_client.getblockchaininfo.return_value = {'chain': 'test'}
		mock_local_client.return_value = local_client
		mock_public_client.return_value = public_client

		routed_client = rpc_client.RoutedEvrmoreClient()
		rpc_client.set_active_network_mode('testnet')
		rpc_client.set_active_rpc_endpoint_mode('local')
		result = routed_client.getblockchaininfo()

		self.assertEqual(result, {'chain': 'test'})
		local_client.getblockchaininfo.assert_called_once()
		public_client.getblockchaininfo.assert_called_once()

	@patch('Tome.rpc_client.RoutedEvrmoreClient._get_public_client')
	@patch('Tome.rpc_client.RoutedEvrmoreClient._get_local_client')
	def test_public_failure_falls_back_to_local(self, mock_local_client, mock_public_client):
		local_client = MagicMock()
		public_client = MagicMock()

		public_client.getblockchaininfo.side_effect = Exception('public endpoint timeout')
		local_client.getblockchaininfo.return_value = {'chain': 'main'}
		mock_local_client.return_value = local_client
		mock_public_client.return_value = public_client

		routed_client = rpc_client.RoutedEvrmoreClient()
		rpc_client.set_active_network_mode('mainnet')
		rpc_client.set_active_rpc_endpoint_mode('public')
		result = routed_client.getblockchaininfo()

		self.assertEqual(result, {'chain': 'main'})
		public_client.getblockchaininfo.assert_called_once()
		local_client.getblockchaininfo.assert_called_once()
