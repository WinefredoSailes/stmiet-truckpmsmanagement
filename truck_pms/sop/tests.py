from django.test import TestCase
from django.urls import reverse


class SopViewTests(TestCase):
    def test_download_page_loads(self):
        resp = self.client.get(reverse('sop:download_page'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'SOP')

    def test_view_en_loads(self):
        resp = self.client.get(reverse('sop:view_en'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Safety')

    def test_view_tl_loads(self):
        resp = self.client.get(reverse('sop:view_tl'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Safety')

    def test_download_en_html(self):
        resp = self.client.get(reverse('sop:download_en'))
        self.assertIn(resp.status_code, (200, 302, 404))

    def test_download_tl_html(self):
        resp = self.client.get(reverse('sop:download_tl'))
        self.assertIn(resp.status_code, (200, 302, 404))
