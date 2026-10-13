import unittest
from pathlib import Path
from app.routes.web.documents import ALLOWED_EXTENSIONS

class TestDocumentExtensions(unittest.TestCase):
    def test_allowed_extensions(self):
        expected_extensions = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png'}
        self.assertEqual(ALLOWED_EXTENSIONS, expected_extensions)

    def test_image_extensions_supported(self):
        self.assertIn('.jpg', ALLOWED_EXTENSIONS)
        self.assertIn('.jpeg', ALLOWED_EXTENSIONS)
        self.assertIn('.png', ALLOWED_EXTENSIONS)

    def test_office_extensions_supported(self):
        self.assertIn('.pdf', ALLOWED_EXTENSIONS)
        self.assertIn('.doc', ALLOWED_EXTENSIONS)
        self.assertIn('.docx', ALLOWED_EXTENSIONS)
        self.assertIn('.xls', ALLOWED_EXTENSIONS)
        self.assertIn('.xlsx', ALLOWED_EXTENSIONS)

    def test_unsupported_extensions(self):
        unsupported = ['test.exe', 'script.sh', 'notes.txt', 'archive.zip']
        for filename in unsupported:
            ext = Path(filename).suffix.lower()
            self.assertNotIn(ext, ALLOWED_EXTENSIONS)

if __name__ == '__main__':
    unittest.main()
