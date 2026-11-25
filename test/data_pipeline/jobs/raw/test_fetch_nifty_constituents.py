import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import polars as pl

from data_pipeline.jobs.raw.fetch_nifty_constituents import (
    fetch_nifty_constituents,
    main,
)
from utils.constants import Index


class TestFetchNiftyConstituents(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_payload = {
            "data": {
                "data": [
                    {
                        "priority": 1,
                        "symbol": "NIFTY 50",
                        "series": None,
                        "lastPrice": 25819.25,
                        "companyName": None,
                    },
                    {
                        "priority": 0,
                        "symbol": "HDFCBANK",
                        "series": "EQ",
                        "lastPrice": 846.2,
                        "companyName": "HDFC BANK LIMITED",
                    },
                    {
                        "priority": 0,
                        "symbol": "ICICIBANK",
                        "series": "EQ",
                        "lastPrice": 1640.0,
                        "companyName": "ICICI BANK LIMITED",
                    },
                ]
            }
        }

    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents.nsefetch")
    def test_fetch_filters_index_summary_and_returns_polars_df(self, mock_nsefetch) -> None:
        mock_nsefetch.return_value = self.sample_payload

        df = fetch_nifty_constituents(Index.NIFTY_50)

        mock_nsefetch.assert_called_once_with(
            "https://www.nseindia.com/api/NextApi/apiClient/marketWatchApi"
            "?functionName=getIndicesData&symbol=NIFTY%2050"
        )
        self.assertIsInstance(df, pl.DataFrame)
        self.assertEqual(df.height, 2)
        self.assertEqual(df["symbol"].to_list(), ["HDFCBANK", "ICICIBANK"])

    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents.nsefetch")
    def test_fetch_normalizes_lowercase_string(self, mock_nsefetch) -> None:
        mock_nsefetch.return_value = self.sample_payload

        df = fetch_nifty_constituents("  nifty 50  ")

        mock_nsefetch.assert_called_once_with(
            "https://www.nseindia.com/api/NextApi/apiClient/marketWatchApi"
            "?functionName=getIndicesData&symbol=NIFTY%2050"
        )
        self.assertEqual(df.height, 2)

    def test_empty_index_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            fetch_nifty_constituents("   ")

    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents.nsefetch")
    def test_empty_response_raises(self, mock_nsefetch) -> None:
        mock_nsefetch.return_value = {"data": {"data": []}}

        with self.assertRaises(ValueError):
            fetch_nifty_constituents("UNKNOWN INDEX")

    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents.nsefetch")
    def test_main_writes_csv(self, mock_nsefetch) -> None:
        mock_nsefetch.return_value = self.sample_payload

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "nifty_50.csv"
            written = main(index_name=Index.NIFTY_50, output_path=out_path)

            self.assertEqual(written, out_path)
            self.assertTrue(out_path.is_file())
            loaded = pl.read_csv(out_path)
            self.assertEqual(loaded["symbol"].to_list(), ["HDFCBANK", "ICICIBANK"])


if __name__ == "__main__":
    unittest.main()
