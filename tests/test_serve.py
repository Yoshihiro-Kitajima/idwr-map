import unittest
from idwr.serve import allowed_update

class UpdateAccessTests(unittest.TestCase):
    def test_same_origin_explicit_button_allowed(self):
        headers={'Host':'127.0.0.1:12345','Origin':'http://127.0.0.1:12345','X-IDWR-Update':'1'}
        self.assertTrue(allowed_update(headers,12345))
    def test_external_page_and_missing_header_rejected(self):
        headers={'Host':'127.0.0.1:12345','Origin':'https://example.org','X-IDWR-Update':'1'}
        self.assertFalse(allowed_update(headers,12345))
        self.assertFalse(allowed_update({'Host':'127.0.0.1:12345','Origin':'http://127.0.0.1:12345'},12345))
