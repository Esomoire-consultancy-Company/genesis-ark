import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from source_integrity import inspect_file, is_text_path


class SourceIntegrityTests(unittest.TestCase):
    def test_ascii_and_multilingual_html_are_valid_utf8(self):
        self.assertEqual(inspect_file(Path('index.html'), b'<meta charset="utf-8">')['status'], 'VALID_UTF8')
        sample = '<svg>مرحبا नमस्ते</svg>'.encode('utf-8')
        self.assertEqual(inspect_file(Path('atlas.svg'), sample)['status'], 'VALID_UTF8')

    def test_non_utf8_text_is_rejected(self):
        entry = inspect_file(Path('diagram.mmd'), b'graph LR\n A--\xe9-->B')
        self.assertEqual(entry['status'], 'INVALID_UTF8')
        self.assertEqual(entry['error_byte'], 13)

    def test_nul_bytes_in_source_are_rejected(self):
        self.assertEqual(inspect_file(Path('schema.json'), b'{}\x00')['status'], 'NUL_IN_TEXT')

    def test_bom_is_limited_to_csv_exports(self):
        bom = b'\xef\xbb\xbf'
        self.assertEqual(inspect_file(Path('REGISTRY.csv'), bom + b'a,b')['status'], 'VALID_UTF8')
        self.assertEqual(inspect_file(Path('code.py'), bom + b'x=1')['status'], 'BOM_IN_SOURCE')

    def test_binary_is_not_forced_to_ascii_or_utf8(self):
        self.assertFalse(is_text_path(Path('design.png')))
        self.assertEqual(inspect_file(Path('design.png'), b'\x89PNG\r\n')['status'], 'NOT_TEXT_CHECKED')


if __name__ == '__main__':
    unittest.main()
