from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.contrib.messages import get_messages

from Wallet import rpc, views
from Wallet.models import UserWallet, WalletAddress, WalletProfile
from Wallet.rip10 import (
    RIP10ValidationError,
    asset_matches_address,
    build_address_metadata_asset,
    build_address_name_tag,
    build_encryption_tag,
    build_signed_metadata,
    parse_address_metadata_asset,
    validate_metadata,
)


class RIP10AddressMetadataTests(TestCase):
    address = 'EL5MFdaF8msRaUEDu9mxSNniPSswNmNRgq'

    def test_address_metadata_asset_round_trip_and_signed_ant_metadata(self):
        asset = build_address_metadata_asset('TOMETAGS', 'ANT', self.address)
        metadata = build_signed_metadata(
            build_address_name_tag(self.address, 'DeFi Tome'),
            'metadata-signature',
        )

        self.assertEqual(asset.asset_name, 'TOMETAGS#ANT_C38D582B')
        self.assertEqual(parse_address_metadata_asset(asset.asset_name), asset)
        self.assertTrue(asset_matches_address(asset.asset_name, self.address))
        self.assertTrue(validate_metadata(asset.asset_name, self.address, metadata).is_valid)

    def test_pgp_asset_uses_aet_metadata_type_and_revision_is_supported(self):
        asset = build_address_metadata_asset('TOMETAGS', 'PGP', self.address, revision='2')
        metadata = build_signed_metadata(
            build_encryption_tag(self.address, '-----BEGIN PGP PUBLIC KEY BLOCK-----\nkey'),
            'metadata-signature',
        )

        self.assertEqual(asset.asset_name, 'TOMETAGS#PGP_C38D582B2')
        self.assertTrue(validate_metadata(asset.asset_name, self.address, metadata).is_valid)

        maximum_length_asset = build_address_metadata_asset(
            'TOMETAGMAX',
            'AIT',
            self.address,
            revision='REVISE7',
        )
        self.assertEqual(len(maximum_length_asset.asset_name), 30)

    def test_invalid_asset_format_is_rejected(self):
        with self.assertRaises(RIP10ValidationError):
            build_address_metadata_asset('TOO-LONG-ASSET', 'ANT', self.address)

        with self.assertRaises(RIP10ValidationError):
            parse_address_metadata_asset('TOMETAGS#ANT_NOT-A-CRC')


class UniqueAssetIssuanceTests(TestCase):
    @patch('Wallet.rpc.create_and_send_asset_operation_transaction', return_value={'txid': 'tag-txid'})
    def test_issue_unique_accepts_explicit_signing_keys(self, mock_create_and_send):
        result = rpc.create_and_send_issue_unique_transaction(
            from_address='owner-address',
            issuer_address='recipient-address',
            root_name='TOMETAGS',
            asset_tags=['ANT_C38D582B'],
            ipfs_hashes=['QmMetadataCid'],
            owner_change_address='owner-address',
            wif_keys=['owner-wif'],
        )

        self.assertEqual(result, {'txid': 'tag-txid'})
        self.assertEqual(mock_create_and_send.call_args.kwargs['wif_keys'], ['owner-wif'])


class RawTransactionBuilderTests(TestCase):
    @patch('Wallet.rpc.sign_and_broadcast_raw_transaction')
    @patch('Wallet.rpc.create_raw_transaction', return_value='rawhex')
    @patch('Wallet.rpc._select_evr_inputs', return_value=([{'txid': 'tx1', 'vout': 0}], 200000000))
    def test_create_raw_evr_transaction_returns_details_without_broadcasting(
        self,
        mock_select_evr_inputs,
        mock_create_raw_transaction,
        mock_sign_and_broadcast,
    ):
        result = rpc.create_raw_evr_transaction(
            from_address='from-address',
            to_address='to-address',
            amount_evr=Decimal('1.5'),
            change_address='change-address',
            fee_evr=Decimal('0.0001'),
        )

        self.assertEqual(result['raw_tx'], 'rawhex')
        self.assertEqual(result['inputs'], [{'txid': 'tx1', 'vout': 0}])
        self.assertIn('to-address', result['outputs'])
        self.assertIn('change-address', result['outputs'])
        mock_sign_and_broadcast.assert_not_called()


class AtomicAssetSwapTransactionTests(TestCase):
    @patch('Wallet.rpc.sign_and_broadcast_raw_transaction', return_value='atomic-swap-txid')
    @patch('Wallet.rpc.create_raw_transaction', return_value='raw-atomic-swap')
    @patch('Wallet.rpc._get_address_utxos')
    def test_atomic_asset_for_evr_swap_uses_one_signed_transaction(
        self,
        mock_get_address_utxos,
        mock_create_raw_transaction,
        mock_sign_and_broadcast,
    ):
        mock_get_address_utxos.side_effect = [
            [
                {
                    'txid': 'seller-asset-tx',
                    'outputIndex': 0,
                    'satoshis': 546,
                    'assetName': 'COLLECTIBLE#1',
                    'assetAmount': '2',
                }
            ],
            [
                {
                    'txid': 'buyer-evr-tx',
                    'outputIndex': 1,
                    'satoshis': 200000000,
                }
            ],
        ]

        result = rpc.create_and_send_atomic_asset_evr_swap_transaction(
            seller_address='seller-address',
            buyer_address='buyer-address',
            asset_name='COLLECTIBLE#1',
            asset_quantity=Decimal('1'),
            payment_evr=Decimal('1'),
            fee_evr=Decimal('0.0001'),
            wif_keys=['seller-wif', 'buyer-wif'],
        )

        self.assertEqual(result['txid'], 'atomic-swap-txid')
        self.assertEqual(result['raw_tx'], 'raw-atomic-swap')
        self.assertEqual(result['asset_change_quantity'], Decimal('1'))
        self.assertEqual(len(result['inputs']), 2)
        self.assertIn(
            {'buyer-address': {'transfer': {'COLLECTIBLE#1': 1.0}}},
            result['outputs'],
        )
        self.assertIn(
            {'seller-address': {'transfer': {'COLLECTIBLE#1': 1.0}}},
            result['outputs'],
        )
        mock_create_raw_transaction.assert_called_once()
        mock_sign_and_broadcast.assert_called_once_with(
            'raw-atomic-swap',
            wif_keys=['seller-wif', 'buyer-wif'],
        )


class WalletTransactionsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='history-user',
            email='history@example.com',
            password='testpass123',
        )
        self.user_wallet = UserWallet.objects.create(
            user=self.user,
            name='History Wallet',
            entropy='test-entropy',
            passphrase='',
        )
        WalletAddress.objects.create(
            wallet=self.user_wallet,
            network_mode='testnet',
            address='EHistoryAddress123',
            wif='L1historywif',
            account=0,
            index=0,
            is_change=False,
        )
        WalletAddress.objects.create(
            wallet=self.user_wallet,
            network_mode='testnet',
            address='EHistoryChange456',
            wif='L1historychangewif',
            account=0,
            index=1,
            is_change=True,
        )

    def test_portfolio_links_to_wallet_transactions(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('portfolio'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('wallet_transactions'))

    @patch('Wallet.views._active_network_mode', return_value='testnet')
    @patch('Wallet.views.RPC.getrawtransaction')
    @patch('Wallet.views.RPC.getaddressdeltas')
    @patch('Wallet.views.RPC.getaddresstxids')
    def test_wallet_transactions_page_renders_history(
        self,
        mock_getaddresstxids,
        mock_getaddressdeltas,
        mock_getrawtransaction,
        mock_network_mode,
    ):
        self.client.force_login(self.user)
        mock_getaddresstxids.return_value = ['tx-older', 'tx-old', 'tx-new']
        mock_getaddressdeltas.return_value = [
            {'txid': 'tx-old', 'satoshis': -250000000},
            {'txid': 'tx-new', 'satoshis': 125000000},
            {'txid': 'tx-new', 'assetName': 'TST', 'assetAmount': '3'},
            {'txid': 'tx-older', 'satoshis': 100000000},
        ]
        mock_getrawtransaction.side_effect = [
            {'confirmations': 6, 'time': 1722900000, 'size': 212},
            {'confirmations': 12, 'time': 1722800000, 'size': 190},
            {'confirmations': 20, 'time': 1722700000, 'size': 188},
        ]

        response = self.client.get(reverse('wallet_transactions'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'portfolio/transactions.html')
        transactions = response.context['transactions']
        self.assertEqual([item['txid'] for item in transactions], ['tx-new', 'tx-old', 'tx-older'])
        self.assertEqual(response.context['address_count'], 2)
        self.assertEqual(response.context['total_indexed_transactions'], 3)
        self.assertFalse(response.context['has_more_transactions'])
        self.assertIsNone(response.context['limit'])
        self.assertTrue(response.context['showing_all_transactions'])
        self.assertEqual(transactions[0]['direction'], 'received')
        self.assertEqual(transactions[0]['evr_delta_display'], '+1.25000000 EVR')
        self.assertEqual(transactions[0]['asset_changes'][0]['amount_display'], '+3 TST')
        self.assertEqual(transactions[1]['direction'], 'sent')
        self.assertEqual(transactions[1]['evr_delta_display'], '-2.50000000 EVR')
        mock_getaddresstxids.assert_called_once_with({'addresses': ['EHistoryAddress123', 'EHistoryChange456']})
        mock_network_mode.assert_called()


class SendFundsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='send-user',
            email='send@example.com',
            password='testpass123',
        )
        self.user_wallet = UserWallet.objects.create(
            user=self.user,
            name='Send Wallet',
            entropy='send-entropy',
            passphrase='',
        )
        WalletAddress.objects.create(
            wallet=self.user_wallet,
            network_mode='testnet',
            address='ESendAddress123',
            wif='L1sendwif',
            account=0,
            index=0,
            is_change=False,
        )

    @patch('Wallet.views._active_network_mode', return_value='testnet')
    def test_get_user_primary_address_prefers_main_profile(self, mock_network_mode):
        first_address = WalletAddress.objects.get(wallet=self.user_wallet, index=0, is_change=False)
        second_address = WalletAddress.objects.create(
            wallet=self.user_wallet,
            network_mode='testnet',
            address='ESendAddress456',
            wif='L1sendwif2',
            account=0,
            index=1,
            is_change=False,
        )
        WalletProfile.objects.create(
            wallet=self.user_wallet,
            address=first_address,
            network_mode='testnet',
            name='Primary',
            is_main=False,
        )
        WalletProfile.objects.create(
            wallet=self.user_wallet,
            address=second_address,
            network_mode='testnet',
            name='Trading',
            is_main=True,
        )

        primary_address = views._get_user_primary_address(self.user)

        self.assertEqual(primary_address, 'ESendAddress456')

    @patch('Wallet.views._active_network_mode', return_value='testnet')
    @patch('Wallet.views.RPC.importprivkey')
    def test_create_profile_derives_next_external_address(self, mock_importprivkey, mock_network_mode):
        self.client.force_login(self.user)
        WalletProfile.objects.create(
            wallet=self.user_wallet,
            address=WalletAddress.objects.get(wallet=self.user_wallet, index=0, is_change=False),
            network_mode='testnet',
            name='Main',
            is_main=True,
        )

        response = self.client.post(
            reverse('send_funds'),
            {
                'action': 'create_profile',
                'profile_name': 'Treasury',
            },
        )

        self.assertEqual(response.status_code, 302)
        created_profile = WalletProfile.objects.get(wallet=self.user_wallet, name='Treasury')
        self.assertEqual(created_profile.address.index, 1)
        self.assertFalse(created_profile.is_main)
        self.assertTrue(created_profile.address.address)
        mock_importprivkey.assert_called_once()

    @patch('Wallet.views._active_network_mode', return_value='testnet')
    def test_set_main_profile_updates_send_receive_source(self, mock_network_mode):
        self.client.force_login(self.user)
        first_address = WalletAddress.objects.get(wallet=self.user_wallet, index=0, is_change=False)
        second_address = WalletAddress.objects.create(
            wallet=self.user_wallet,
            network_mode='testnet',
            address='ESendAddress456',
            wif='L1sendwif2',
            account=0,
            index=1,
            is_change=False,
        )
        WalletProfile.objects.create(
            wallet=self.user_wallet,
            address=first_address,
            network_mode='testnet',
            name='Main',
            is_main=True,
        )
        profile = WalletProfile.objects.create(
            wallet=self.user_wallet,
            address=second_address,
            network_mode='testnet',
            name='Trading',
            is_main=False,
        )

        response = self.client.post(
            reverse('send_funds'),
            {
                'action': 'set_main_profile',
                'profile_id': str(profile.id),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertTrue(profile.is_main)
        self.assertEqual(views._get_user_primary_address(self.user), 'ESendAddress456')
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn('"Trading" is now your main wallet profile.', messages)

    @patch('Wallet.views._active_network_mode', return_value='testnet')
    @patch('Wallet.views.build_qr_data_uri', return_value='data:image/png;base64,abc')
    @patch('Wallet.views._sync_user_evr_balance', return_value=Decimal('100000000'))
    @patch('Wallet.views._get_user_asset_balances', return_value=({'WHOLE': Decimal('2')}, None))
    @patch('Wallet.views._get_asset_units', return_value=0)
    def test_send_funds_context_includes_asset_divisibility_metadata(
        self,
        mock_get_asset_units,
        mock_get_user_asset_balances,
        mock_sync_balance,
        mock_build_qr,
        mock_network_mode,
    ):
        self.client.force_login(self.user)

        response = self.client.get(reverse('send_funds'))

        self.assertEqual(response.status_code, 200)
        asset_option = response.context['asset_options'][0]
        self.assertEqual(asset_option['symbol'], 'WHOLE')
        self.assertEqual(asset_option['units'], 0)
        self.assertEqual(asset_option['step'], '1')
        self.assertEqual(asset_option['min_value'], '1')

    @patch('Wallet.views._active_network_mode', return_value='testnet')
    @patch('Wallet.views.build_qr_data_uri', return_value='data:image/png;base64,abc')
    @patch('Wallet.views._sync_user_evr_balance', return_value=Decimal('100000000'))
    @patch('Wallet.views._get_user_asset_balances', return_value=({'WHOLE': Decimal('2')}, None))
    @patch('Wallet.views._get_asset_units', return_value=0)
    @patch('Wallet.views.create_and_send_asset_transfer_transaction')
    def test_send_funds_rejects_fractional_amount_for_indivisible_asset(
        self,
        mock_send_asset,
        mock_get_asset_units,
        mock_get_user_asset_balances,
        mock_sync_balance,
        mock_build_qr,
        mock_network_mode,
    ):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('send_funds'),
            {
                'currency': 'WHOLE',
                'recipient_address': 'ERecipient123',
                'amount': '1.5',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This asset is indivisible and must be sent as a whole number.')
        mock_send_asset.assert_not_called()

    @patch('Wallet.views._active_network_mode', return_value='testnet')
    @patch('Wallet.views.build_qr_data_uri', return_value='data:image/png;base64,abc')
    @patch('Wallet.views._sync_user_evr_balance', return_value=Decimal('100000000'))
    @patch('Wallet.views._get_user_asset_balances', return_value=({'WHOLE': Decimal('2')}, None))
    @patch('Wallet.views._get_asset_units', return_value=0)
    @patch('Wallet.views._get_wallet_profiles', return_value=[])
    @patch('Wallet.views._get_or_create_main_wallet_profile', return_value=None)
    @patch('Wallet.views._get_user_primary_address', return_value='ESendAddress123')
    @patch('Wallet.views._derive_user_wif_for_address', return_value='L1sendwif')
    @patch('Wallet.views._ensure_change_wallet_address')
    @patch('Wallet.views.create_and_send_asset_transfer_transaction', return_value={'txid': 'asset-txid'})
    def test_send_funds_uses_distinct_change_address_for_asset_transfers(
        self,
        mock_send_asset,
        mock_ensure_change_address,
        mock_derive_wif,
        mock_get_primary_address,
        mock_main_profile,
        mock_wallet_profiles,
        mock_get_asset_units,
        mock_get_user_asset_balances,
        mock_sync_balance,
        mock_build_qr,
        mock_network_mode,
    ):
        self.client.force_login(self.user)
        mock_ensure_change_address.return_value = type('ChangeAddress', (), {'address': 'EChangeAddress789'})()

        response = self.client.post(
            reverse('send_funds'),
            {
                'currency': 'WHOLE',
                'recipient_address': 'ERecipient123',
                'amount': '1',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_send_asset.called, response.content.decode())
        called_kwargs = mock_send_asset.call_args.kwargs
        self.assertEqual(called_kwargs['from_address'], 'ESendAddress123')
        self.assertEqual(called_kwargs['asset_change_address'], 'ESendAddress123')
        self.assertEqual(called_kwargs['change_address'], 'EChangeAddress789')
        self.assertEqual(called_kwargs['wif_keys'], ['L1sendwif'])
        self.assertContains(response, 'Successfully sent 1 to ERecipient123. Transaction ID: asset-txid')

    @patch('Wallet.views.RPC.getassetdata', return_value={'units': 8})
    def test_get_asset_units_forces_admin_assets_to_be_indivisible(self, mock_getassetdata):
        self.assertEqual(views._get_asset_units('ROOT!'), 0)
        mock_getassetdata.assert_not_called()

    @patch('Wallet.views.RPC.getassetdata', return_value=None)
    @patch('Wallet.views._active_network_mode', return_value='testnet')
    def test_get_asset_units_uses_tracked_asset_for_active_network(self, mock_network_mode, mock_getassetdata):
        from Wallet.models import TrackedAsset

        TrackedAsset.objects.create(symbol='SAME', network_mode='mainnet', units=2)
        TrackedAsset.objects.create(symbol='SAME', network_mode='testnet', units=5)

        self.assertEqual(views._get_asset_units('SAME'), 5)
