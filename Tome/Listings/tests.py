from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from DeFi.models import SwapOffer
from .models import Listing, NFT


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
