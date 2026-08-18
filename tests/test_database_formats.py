from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from qasas.database_formats import (
    COV_ABDAB_DATABASE_FORMAT,
    DATABASE_FORMAT_CHOICES,
    GENERIC_DATABASE_FORMAT,
    database_format_label,
    resolve_database_format,
)
from qasas.loaders import load_database


class DatabaseFormatTests(unittest.TestCase):
    def test_choices_expose_cov_abdab_and_disabled_generic_placeholder(self):
        self.assertEqual(
            [choice.value for choice in DATABASE_FORMAT_CHOICES],
            [COV_ABDAB_DATABASE_FORMAT, GENERIC_DATABASE_FORMAT],
        )
        self.assertEqual([choice.enabled for choice in DATABASE_FORMAT_CHOICES], [True, False])
        self.assertEqual(database_format_label(COV_ABDAB_DATABASE_FORMAT), "CoV-AbDab（CSV）")
        self.assertEqual(
            database_format_label(GENERIC_DATABASE_FORMAT),
            "汎用データベース（今後対応）",
        )

    def test_cov_abdab_selection_is_supported(self):
        self.assertEqual(
            resolve_database_format(COV_ABDAB_DATABASE_FORMAT),
            COV_ABDAB_DATABASE_FORMAT,
        )

    def test_generic_placeholder_cannot_reach_the_loader(self):
        with self.assertRaisesRegex(ValueError, "今後対応予定"):
            resolve_database_format(GENERIC_DATABASE_FORMAT)

    def test_loader_records_selected_database_format(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "database.csv"
            path.write_text(
                "Heavy V Gene,Heavy J Gene,CDRH3,Name\n"
                "IGHV1-2*01,IGHJ4*02,ARDR,Example antibody\n",
                encoding="utf-8",
            )
            database = load_database(
                path,
                database_format=COV_ABDAB_DATABASE_FORMAT,
            )
            self.assertEqual(
                database.metadata["Database input format"],
                COV_ABDAB_DATABASE_FORMAT,
            )


if __name__ == "__main__":
    unittest.main()
