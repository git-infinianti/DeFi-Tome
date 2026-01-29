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
    
    def test_explorer_page_content(self):
        """Test that the explorer page contains expected content"""
        response = self.client.get(reverse('explorer'))
        self.assertContains(response, 'Blockchain Explorer')
        self.assertContains(response, 'View the 10 most recent blocks')
