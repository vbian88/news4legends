import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))

from collector import generic_relevance, title_is_generic


class CollectorRelevanceTests(unittest.TestCase):
    def test_phrase_and_whole_token_matching(self):
        self.assertEqual("ACCEPT", generic_relevance(
            "Premier League transfer update", "", "Premier League", [], []
        )[0])
        self.assertEqual("REJECT", generic_relevance(
            "Premierly written story", "", "Premier", [], []
        )[0])

    def test_tri_state_and_static_title(self):
        self.assertEqual("AMBIGUOUS", generic_relevance(
            "Security weekly", "", "Cybersecurity", ["weekly"], []
        )[0])
        self.assertEqual("REJECT", generic_relevance(
            "Unrelated weather", "Cloud and rain", "Cybersecurity", [], []
        )[0])
        self.assertTrue(title_is_generic("Privacy Policy"))


if __name__ == "__main__":
    unittest.main()
