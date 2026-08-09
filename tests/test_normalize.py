import unittest

from qasas.engine import bounded_levenshtein
from qasas.normalize import normalize_cdr3, normalize_gene_options


class NormalizeTests(unittest.TestCase):
    def test_gene_allele_and_species_are_removed(self):
        self.assertEqual(normalize_gene_options("IGHV3-23*01 (Human)", "IGHV"), ("IGHV3-23",))
        self.assertEqual(normalize_gene_options("IGHJ4*02", "IGHJ"), ("IGHJ4",))
        self.assertEqual(normalize_gene_options("IHGJ4 (Human)", "IGHJ"), ("IGHJ4",))

    def test_ambiguous_gene_options_are_kept(self):
        self.assertEqual(
            normalize_gene_options("IGHV3-30*01 // IGHV3-30-3*02, IGHV3-30*04", "IGHV"),
            ("IGHV3-30", "IGHV3-30-3"),
        )

    def test_cdr3_anchors_are_harmonized(self):
        self.assertEqual(normalize_cdr3("CARDRSTGW"), "ARDRSTG")
        self.assertEqual(normalize_cdr3("ARDRSTG"), "ARDRSTG")

    def test_bounded_levenshtein(self):
        self.assertEqual(bounded_levenshtein("ABCDE", "ABCDE", 2), 0)
        self.assertEqual(bounded_levenshtein("ABCDE", "ABCXE", 2), 1)
        self.assertEqual(bounded_levenshtein("ABCDE", "ABXYE", 2), 2)
        self.assertEqual(bounded_levenshtein("ABCDE", "AXYZE", 2), 3)


if __name__ == "__main__":
    unittest.main()
