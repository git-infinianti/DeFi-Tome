from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from Wallet import rpc


class RawTransactionBuilderTests(TestCase):
    @patch('Wallet.rpc.sign_and_broadcast_raw_transaction')
    @patch('Wallet.rpc.create_raw_transaction', return_value='rawhex')
    @patch('Wallet.rpc._select_evr_inputs', return_value=([{'txid': 'tx1', 'vout': 0}], 20000000))
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
