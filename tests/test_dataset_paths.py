import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest


class DatasetPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp_dir.name) / 'dataset'
        cls.root.mkdir()
        (cls.root / 'sample.txt').write_text('sample media', encoding='utf-8')
        (cls.root / 'sample.caption_txt').write_text('old caption', encoding='utf-8')

        app_path = Path(__file__).resolve().parents[1] / 'app.py'
        old_argv = sys.argv
        old_cwd = Path.cwd()
        try:
            sys.argv = [str(app_path), str(cls.root), '--no-login']
            os.chdir(cls.temp_dir.name)
            spec = importlib.util.spec_from_file_location('data_viewer_test_app', app_path)
            cls.module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = cls.module
            spec.loader.exec_module(cls.module)
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop('data_viewer_test_app', None)
        cls.temp_dir.cleanup()

    def test_resolve_data_path_rejects_parent_traversal(self):
        with self.assertRaises(ValueError):
            self.module.resolve_data_path('../outside.txt')

    def test_save_rejects_annotation_outside_dataset(self):
        outside = self.root.parent / 'outside.txt'
        response = self.module.app.test_client().post(
            '/api/item/0',
            json={
                'annotations': [
                    {'filename': '../outside.txt', 'content': 'escaped'}
                ]
            },
        )

        self.assertEqual(400, response.status_code)
        self.assertFalse(outside.exists())

    def test_save_allows_an_annotation_inside_dataset(self):
        response = self.module.app.test_client().post(
            '/api/item/0',
            json={
                'annotations': [
                    {'filename': 'sample.caption_txt', 'content': 'new caption'}
                ]
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            'new caption',
            (self.root / 'sample.caption_txt').read_text(encoding='utf-8'),
        )


if __name__ == '__main__':
    unittest.main()
