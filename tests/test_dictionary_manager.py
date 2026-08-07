import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from managers.dictionary_manager import DictionaryManager


class TestDictionaryManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "dictionary.json"
        data = {
            "Docker": {
                "translations": {"tha_Thai": "Docker"},
                "do_not_translate": True,
            },
            "install": {
                "translations": {"tha_Thai": "ติดตั้ง"},
                "do_not_translate": False,
            },
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_and_protect(self):
        mgr = DictionaryManager(self.path)
        self.assertIn("Docker", mgr.dictionary)

    def test_apply_translation(self):
        mgr = DictionaryManager(self.path)
        result = mgr.apply("Please install Docker", "tha_Thai")
        self.assertIn("ติดตั้ง", result)
        self.assertIn("Docker", result)

    def test_apply_no_target(self):
        mgr = DictionaryManager(self.path)
        result = mgr.apply("Please install Docker")
        self.assertEqual(result, "Please install Docker")


if __name__ == "__main__":
    unittest.main()
