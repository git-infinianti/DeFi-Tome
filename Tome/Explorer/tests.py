from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from Explorer import views


class ExplorerViewTests(TestCase):
    """Tests for the Explorer app views"""
    
    def test_explorer_page_accessible(self):
        """Test that the explorer page is accessible"""
        response = self.client.get(reverse('explorer'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'explorer/index.html')
    
    def test_explorer_page_context(self):
        """Test that the explorer page has the required context"""
        response = self.client.get(reverse('explorer'))
        self.assertIn('blocks', response.context)
        self.assertIn('error_message', response.context)
        self.assertIn('page', response.context)
        self.assertIn('has_next', response.context)
        self.assertIn('has_prev', response.context)
    
    def test_explorer_page_content(self):
        """Test that the explorer page contains expected content"""
        response = self.client.get(reverse('explorer'))
        self.assertContains(response, 'Blockchain Explorer')
        self.assertContains(response, 'View recent blocks on the blockchain')
    
    def test_explorer_pagination_default_page(self):
        """Test that the explorer defaults to page 1"""
        response = self.client.get(reverse('explorer'))
        self.assertEqual(response.context['page'], 1)
    
    def test_explorer_pagination_specific_page(self):
        """Test that the explorer respects the page parameter"""
        response = self.client.get(reverse('explorer') + '?page=2')
        self.assertEqual(response.context['page'], 2)
    
    def test_explorer_pagination_invalid_page(self):
        """Test that the explorer handles invalid page numbers gracefully"""
        response = self.client.get(reverse('explorer') + '?page=invalid')
        self.assertEqual(response.context['page'], 1)
        
        response = self.client.get(reverse('explorer') + '?page=-1')
        self.assertEqual(response.context['page'], 1)
    
    def test_explorer_pagination_boundary_conditions(self):
        """Test that pagination defaults to page 1 and context variables are set"""
        response = self.client.get(reverse('explorer'))
        # When RPC fails or no blocks, page should still be 1
        self.assertEqual(response.context['page'], 1)
        # has_prev should be False on page 1
        self.assertFalse(response.context['has_prev'])


class TransactionOutputNormalizationTests(TestCase):
    def test_normalize_outputs_handles_assets_and_address_shapes(self):
        normalized = views._normalize_transaction_outputs([
            {
                'n': 0,
                'value': '0.00000546',
                'scriptPubKey': {
                    'type': 'transfer_asset',
                    'address': 'EAssetReceiver123',
                    'hex': 'deadbeef',
                    'asset': {
                        'name': 'TOME/ALPHA',
                        'amount': '1',
                        'message': 'QmCID',
                    },
                },
            },
            {
                'n': 1,
                'value': 1,
                'scriptPubKey': {
                    'type': 'pubkeyhash',
                    'addresses': ['EPrimaryAddress123', 'ESecondaryAddress456'],
                    'hex': 'beadfeed',
                },
            },
        ])

        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]['primary_address'], 'EAssetReceiver123')
        self.assertEqual(normalized[0]['asset_name'], 'TOME/ALPHA')
        self.assertEqual(normalized[0]['asset_amount_display'], '1.00000000')
        self.assertEqual(normalized[1]['primary_address'], 'EPrimaryAddress123')
        self.assertEqual(normalized[1]['addresses'][1], 'ESecondaryAddress456')

    def test_output_summary_includes_evr_and_asset_counts(self):
        vout_display = [
            {'evr_value_display': '0.50000000', 'asset_name': 'ASSET1'},
            {'evr_value_display': '1.25000000', 'asset_name': None},
            {'evr_value_display': '0.00000546', 'asset_name': 'ASSET1'},
            {'evr_value_display': '0.00000000', 'asset_name': 'ASSET2'},
        ]

        summary = views._summarize_transaction_outputs(vout_display)

        self.assertEqual(summary['output_count'], 4)
        self.assertEqual(summary['evr_total_display'], '1.75000546')
        self.assertEqual(summary['asset_output_count'], 3)
        self.assertEqual(summary['asset_name_count'], 2)

    @patch('Explorer.views._rpc_call')
    def test_transaction_detail_context_uses_normalized_outputs(self, mock_rpc_call):
        mock_rpc_call.side_effect = [
            {
                'txid': 'tx123',
                'hash': 'hash123',
                'size': 400,
                'version': 2,
                'locktime': 0,
                'blockhash': 'blockhash123',
                'confirmations': 10,
                'time': 1722900000,
                'blocktime': 1722900000,
                'vin': [],
                'vout': [
                    {
                        'n': 0,
                        'value': '0.00000546',
                        'scriptPubKey': {
                            'type': 'transfer_asset',
                            'address': 'EAssetReceiver123',
                            'asset': {'name': 'TOME/BETA', 'amount': '2'},
                            'hex': 'cafebabe',
                        },
                    }
                ],
            },
            {
                'height': 120,
            },
        ]

        response = self.client.get(reverse('transaction_detail', kwargs={'txid': 'tx123'}))

        self.assertEqual(response.status_code, 200)
        tx = response.context['transaction']
        self.assertIn('vout_display', tx)
        self.assertIn('output_summary', tx)
        self.assertEqual(tx['vout_display'][0]['primary_address'], 'EAssetReceiver123')
        self.assertEqual(tx['vout_display'][0]['asset_name'], 'TOME/BETA')
        self.assertEqual(tx['output_summary']['asset_output_count'], 1)
