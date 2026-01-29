from django.test import TestCase
from django.urls import reverse


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
