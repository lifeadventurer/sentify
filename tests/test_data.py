import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from utils import data  # noqa: E402


class CompanySearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mapping_path = Path(self.temp_dir.name) / "companies.json"
        self.mapping_path.write_text(
            json.dumps(
                {
                    "Apple": "AAPL",
                    "AMD": "AMD",
                    "Alphabet (Google)": "GOOG",
                    "Microsoft": "MSFT",
                    "Hermes International": "RMS.PA",
                    "L'Oréal": "OR.PA",
                    "Munich RE (Münchener Rück)": "MUV2.DE",
                }
            )
        )
        self.mapping_patcher = patch.object(
            data,
            "COMPANIES_TO_TICKER_SYMBOL_JSON_FILE",
            str(self.mapping_path),
        )
        self.mapping_patcher.start()

    def tearDown(self) -> None:
        self.mapping_patcher.stop()
        self.temp_dir.cleanup()

    def test_check_company_exists_accepts_suggestion_label(self) -> None:
        company_exists, company = data.check_company_exists("Apple (AAPL)")

        self.assertTrue(company_exists)
        self.assertEqual(("Apple", "AAPL"), company)

    def test_check_company_exists_accepts_ascii_query_for_accented_name(
        self,
    ) -> None:
        company_exists, company = data.check_company_exists("loreal")

        self.assertTrue(company_exists)
        self.assertEqual(("L'Oréal", "OR.PA"), company)

    def test_company_suggestions_match_ticker_prefix(self) -> None:
        suggestions = data.get_company_suggestions("aa")

        self.assertEqual(
            [
                {
                    "company_name": "Apple",
                    "ticker_symbol": "AAPL",
                    "label": "Apple (AAPL)",
                }
            ],
            suggestions,
        )

    def test_company_suggestions_match_company_tokens(self) -> None:
        suggestions = data.get_company_suggestions("goo")

        self.assertEqual(
            [
                {
                    "company_name": "Alphabet (Google)",
                    "ticker_symbol": "GOOG",
                    "label": "Alphabet (Google) (GOOG)",
                }
            ],
            suggestions,
        )

    def test_company_suggestions_limit_results(self) -> None:
        suggestions = data.get_company_suggestions("a", limit=2)

        self.assertEqual(2, len(suggestions))

    def test_company_suggestions_match_ascii_query_for_accented_name(
        self,
    ) -> None:
        suggestions = data.get_company_suggestions("loreal")

        self.assertEqual(
            [
                {
                    "company_name": "L'Oréal",
                    "ticker_symbol": "OR.PA",
                    "label": "L'Oréal (OR.PA)",
                }
            ],
            suggestions,
        )

    def test_company_suggestions_match_transliterated_umlaut_query(
        self,
    ) -> None:
        suggestions = data.get_company_suggestions("muench")

        self.assertEqual(
            [
                {
                    "company_name": "Munich RE (Münchener Rück)",
                    "ticker_symbol": "MUV2.DE",
                    "label": "Munich RE (Münchener Rück) (MUV2.DE)",
                }
            ],
            suggestions,
        )


if __name__ == "__main__":
    unittest.main()
