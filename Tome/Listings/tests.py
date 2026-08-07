from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from DeFi.models import SwapOffer
from Settings.models import MembershipPlan, UserMembership
from .models import Listing, NFT, TradingPair


class AtomicSwapCreationTestCase(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='seller', password='testpass123')
		self.client = Client()

	@patch(
		'Listings.views._get_user_asset_balances',
		return_value=({'COLLECTIBLE#001': Decimal('1')}, None),
	)
	def test_unique_asset_creates_an_nft_atomic_swap(self, mock_asset_balances):
		self.client.login(username='seller', password='testpass123')

		response = self.client.post(
			reverse('create_listing'),
			{
				'title': 'Collection Piece',
				'description': 'An on-chain unique asset.',
				'price': '2',
				'token_offered': 'COLLECTIBLE#001',
				'preferred_token': 'EVR',
				'expiry_days': '7',
			},
		)

		self.assertRedirects(response, reverse('listings'))
		listing = Listing.objects.get()
		nft = NFT.objects.get()
		swap_offer = SwapOffer.objects.get()
		self.assertEqual(listing.token_offered, 'COLLECTIBLE#001')
		self.assertTrue(listing.item.is_nft)
		self.assertEqual(nft.token_id, 'COLLECTIBLE#001')
		self.assertEqual(swap_offer.offer_token, 'COLLECTIBLE#001')
		self.assertEqual(swap_offer.request_token, 'EVR')


class MarketAuthorizationAndNetworkIsolationTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='market-user', password='testpass123')
		self.client = Client()

	@patch('Listings.views._get_user_asset_balances', return_value=({'TESTASSET': Decimal('5')}, None))
	def test_market_creation_requires_authorization(self, _mock_balances):
		self.client.login(username='market-user', password='testpass123')
		response = self.client.post(
			reverse('create_market'),
			{'base_token': 'TESTASSET', 'quote_token': 'EVR'},
		)

		self.assertRedirects(response, reverse('markets'))
		self.assertFalse(TradingPair.objects.exists())

	@patch('Listings.views._get_user_asset_balances', return_value=({'TESTASSET': Decimal('5')}, None))
	def test_authorized_user_can_create_market_on_active_network(self, _mock_balances):
		plan = MembershipPlan.objects.create(
			code='pro',
			name='Pro',
			feature_codes=['market_management'],
		)
		UserMembership.objects.create(user=self.user, plan=plan, status='active')

		self.client.login(username='market-user', password='testpass123')
		response = self.client.post(
			reverse('create_market'),
			{'base_token': 'TESTASSET', 'quote_token': 'EVR'},
		)

		self.assertRedirects(response, reverse('markets'))
		pair = TradingPair.objects.get()
		self.assertEqual(pair.network_mode, 'testnet')

	@patch(
		'Listings.views._get_user_asset_balances',
		return_value=({'TOKEN/ALPHA': Decimal('5'), 'COLLECTIBLE#001': Decimal('1'), 'ADMIN!': Decimal('1')}, None),
	)
	def test_only_token_assets_are_listed_as_market_candidates(self, _mock_balances):
		plan = MembershipPlan.objects.create(
			code='pro-token-listing',
			name='Pro Token Listing',
			feature_codes=['market_management'],
		)
		UserMembership.objects.create(user=self.user, plan=plan, status='active')

		self.client.login(username='market-user', password='testpass123')
		response = self.client.get(reverse('create_market'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['available_base_tokens'], ['TOKEN/ALPHA'])
		self.assertEqual(response.context['available_quote_tokens'], ['EVR', 'TOKEN/ALPHA'])

	@patch('Listings.views._get_user_asset_balances', return_value=({'TOKEN/ALPHA': Decimal('5'), 'COLLECTIBLE#001': Decimal('1'), 'ADMIN!': Decimal('1')}, None))
	def test_unique_and_admin_assets_are_rejected_for_market_creation(self, _mock_balances):
		plan = MembershipPlan.objects.create(
			code='pro-token-reject',
			name='Pro Token Reject',
			feature_codes=['market_management'],
		)
		UserMembership.objects.create(user=self.user, plan=plan, status='active')

		self.client.login(username='market-user', password='testpass123')
		response_unique = self.client.post(
			reverse('create_market'),
			{'base_token': 'COLLECTIBLE#001', 'quote_token': 'EVR'},
		)
		self.assertEqual(response_unique.status_code, 200)
		self.assertContains(response_unique, 'Only token assets can be used as a market base asset. Unique and admin assets are not allowed.')
		self.assertFalse(TradingPair.objects.exists())

		response_admin = self.client.post(
			reverse('create_market'),
			{'base_token': 'ADMIN!', 'quote_token': 'EVR'},
		)
		self.assertEqual(response_admin.status_code, 200)
		self.assertContains(response_admin, 'Only token assets can be used as a market base asset. Unique and admin assets are not allowed.')
		self.assertFalse(TradingPair.objects.exists())

	def test_markets_view_only_shows_current_network(self):
		TradingPair.objects.create(base_token='MAIN', quote_token='EVR', network_mode='mainnet')
		TradingPair.objects.create(base_token='TEST', quote_token='EVR', network_mode='testnet')

		self.client.login(username='market-user', password='testpass123')
		response = self.client.get(reverse('markets'))

		self.assertEqual(response.status_code, 200)
		markets = list(response.context['markets'])
		self.assertEqual(len(markets), 1)
		self.assertEqual(markets[0].base_token, 'TEST')


class SwapOfferNetworkIsolationTests(TestCase):
	def setUp(self):
		self.seller = User.objects.create_user(username='seller-net', password='testpass123')
		self.buyer = User.objects.create_user(username='buyer-net', password='testpass123')
		self.client = Client()

	def test_available_swaps_filters_by_active_network(self):
		SwapOffer.objects.create(
			initiator=self.seller,
			offer_token='ASSET1',
			offer_amount=Decimal('1'),
			request_token='EVR',
			request_amount=Decimal('1'),
			expires_at=timezone.now() + timedelta(days=1),
			network_mode='testnet',
		)
		SwapOffer.objects.create(
			initiator=self.seller,
			offer_token='ASSET2',
			offer_amount=Decimal('1'),
			request_token='EVR',
			request_amount=Decimal('1'),
			expires_at=timezone.now() + timedelta(days=1),
			network_mode='mainnet',
		)

		self.client.login(username='buyer-net', password='testpass123')
		response = self.client.get(reverse('available_swap_offers'))

		self.assertEqual(response.status_code, 200)
		offers = list(response.context['offers'])
		self.assertEqual(len(offers), 1)
		self.assertEqual(offers[0].offer_token, 'ASSET1')
