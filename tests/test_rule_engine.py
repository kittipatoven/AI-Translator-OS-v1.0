import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from managers.rule_engine import RuleEngine


class TestRuleEngine(unittest.TestCase):
    def test_mask_unmask(self):
        rule = RuleEngine()
        text = "I want to install Docker on my Raspberry Pi."
        masked = rule.mask(text)
        self.assertNotIn("Docker", masked)
        self.assertNotIn("Raspberry Pi", masked)
        unmasked = rule.unmask(masked)
        self.assertEqual(unmasked, text)

    def test_custom_terms(self):
        rule = RuleEngine(["MyBrand"])
        text = "Use MyBrand CPU and GPU."
        masked = rule.mask(text)
        self.assertNotIn("MyBrand", masked)
        unmasked = rule.unmask(masked)
        self.assertEqual(unmasked, text)

    def test_no_overlap(self):
        rule = RuleEngine(["GPU", "GPU fan"])
        text = "My GPU fan is loud."
        masked = rule.mask(text)
        # Longest term should be matched first.
        self.assertIn("GPU fan", {rule._placeholders[k] for k in rule._placeholders})


if __name__ == "__main__":
    unittest.main()
