import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from managers.confidence_manager import ConfidenceManager


class TestConfidenceManager(unittest.TestCase):
    def test_high_confidence(self):
        cm = ConfidenceManager(threshold=0.7)
        score = cm.score("Hello", "Hello", 1.0)
        self.assertGreaterEqual(score, 0.9)
        self.assertTrue(cm.is_confident(score))

    def test_low_confidence(self):
        cm = ConfidenceManager(threshold=0.7)
        score = cm.score("Hello", "Completely different text", 0.0)
        self.assertLess(score, 0.7)
        self.assertFalse(cm.is_confident(score))


if __name__ == "__main__":
    unittest.main()
