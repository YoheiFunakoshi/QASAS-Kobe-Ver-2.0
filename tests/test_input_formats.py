from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from qasas.input_formats import (
    AUTO_INPUT_FORMAT,
    CPM_INPUT_FORMAT,
    GENERIC_INPUT_FORMAT,
    INPUT_FORMAT_CHOICES,
    RG_INPUT_FORMAT,
    input_format_label,
    resolve_input_format,
)


class InputFormatTests(unittest.TestCase):
    def test_choices_expose_rg_cpm_and_disabled_generic_placeholder(self):
        self.assertEqual(
            [choice.value for choice in INPUT_FORMAT_CHOICES],
            [RG_INPUT_FORMAT, CPM_INPUT_FORMAT, GENERIC_INPUT_FORMAT],
        )
        self.assertEqual([choice.enabled for choice in INPUT_FORMAT_CHOICES], [True, True, False])
        self.assertEqual(input_format_label(RG_INPUT_FORMAT), "RG社形式（Excel）")
        self.assertEqual(input_format_label(CPM_INPUT_FORMAT), "CPM社形式（CSV/TSV）")
        self.assertEqual(input_format_label(GENERIC_INPUT_FORMAT), "汎用形式（今後対応）")

    def test_auto_detects_rg_from_excel_extension(self):
        self.assertEqual(
            resolve_input_format(AUTO_INPUT_FORMAT, Path("sample.xlsx")),
            RG_INPUT_FORMAT,
        )

    def test_auto_detects_cpm_from_required_headers(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.csv"
            path.write_text("Vseg,Jseg,CDR3,Counts\nIGHV1-2,IGHJ4,CARDRW,1\n", encoding="utf-8")
            self.assertEqual(resolve_input_format(AUTO_INPUT_FORMAT, path), CPM_INPUT_FORMAT)

    def test_explicit_supported_selection_is_preserved(self):
        self.assertEqual(resolve_input_format(RG_INPUT_FORMAT, "sample.csv"), RG_INPUT_FORMAT)
        self.assertEqual(resolve_input_format(CPM_INPUT_FORMAT, "sample.xlsx"), CPM_INPUT_FORMAT)

    def test_generic_placeholder_cannot_reach_the_loader(self):
        with self.assertRaisesRegex(ValueError, "今後対応予定"):
            resolve_input_format(GENERIC_INPUT_FORMAT, "sample.csv")


if __name__ == "__main__":
    unittest.main()
