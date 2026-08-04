from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from Wallet import rpc


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
