import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl

from data_pipeline.jobs.raw.fetch_nifty_constituents_pricing_data import (
    PRICING_COLUMNS,
    fetch_pricing_data,
    main,
)
from IO.adapters.csv_adapter import CSVAdapter
from utils.constants import Index


def _fake_chart_payload(
    ts: int, o: float, h: float, l: float, c: float, adj: float, vol: int
) -> dict:
    return {
        "chart": {
            "result": [
                {
                    "timestamp": [ts],
                    "indicators": {
                        "quote": [
                            {
                                "open": [o],
                                "high": [h],
                                "low": [l],
                                "close": [c],
                                "volume": [vol],
                            }
                        ],
                        "adjclose": [{"adjclose": [adj]}],
                    },
                }
            ]
        }
    }


class TestFetchNiftyConstituentsPricingData(unittest.TestCase):
    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents_pricing_data.get_json_with_retry")
    @patch(
        "data_pipeline.jobs.raw.fetch_nifty_constituents_pricing_data.build_thread_session_getter"
    )
    def test_fetch_pricing_data_parses_matching_ist_date(
        self, mock_session_getter, mock_get_json
    ) -> None:
        mock_session_getter.return_value = lambda: MagicMock()
        ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
        ts = int(dt.datetime(2026, 11, 25, 9, 15, tzinfo=ist).timestamp())
        mock_get_json.side_effect = [
            _fake_chart_payload(ts, 833.1, 850.5, 831.55, 846.2, 840.12345, 48187313),
            _fake_chart_payload(ts, 1359.8, 1394.2, 1357.0, 1373.9, 1373.9, 18781717),
        ]

        df = fetch_pricing_data(["HDFCBANK", "RELIANCE"], "2026-11-25", max_workers=1)

        self.assertEqual(df.columns, PRICING_COLUMNS)
        self.assertEqual(df.height, 2)
        self.assertEqual(df["adjusted_close"].to_list(), [840.1235, 1373.9])
        self.assertEqual(df["volume"].to_list(), [48187313, 18781717])

    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents_pricing_data.get_json_with_retry")
    @patch(
        "data_pipeline.jobs.raw.fetch_nifty_constituents_pricing_data.build_thread_session_getter"
    )
    def test_fetch_pricing_data_raises_when_market_closed(
        self, mock_session_getter, mock_get_json
    ) -> None:
        mock_session_getter.return_value = lambda: MagicMock()
        mock_get_json.return_value = {
            "chart": {"result": [{"timestamp": [], "indicators": {"quote": [{}]}}]}
        }

        with self.assertRaises(ValueError):
            fetch_pricing_data(["HDFCBANK"], "2026-11-22", max_workers=1)

    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents_pricing_data.get_json_with_retry")
    @patch(
        "data_pipeline.jobs.raw.fetch_nifty_constituents_pricing_data.build_thread_session_getter"
    )
    def test_main_writes_pricing_csv(self, mock_session_getter, mock_get_json) -> None:
        mock_session_getter.return_value = lambda: MagicMock()
        ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
        ts = int(dt.datetime(2026, 11, 25, 9, 15, tzinfo=ist).timestamp())
        mock_get_json.side_effect = [
            _fake_chart_payload(ts, 833.1, 850.5, 831.55, 846.2, 846.2, 48187313),
            _fake_chart_payload(ts, 1359.8, 1394.2, 1357.0, 1373.9, 1373.9, 18781717),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            adapter = CSVAdapter()
            adapter.write(
                pl.DataFrame({"symbol": ["HDFCBANK", "RELIANCE"]}),
                Path(tmp) / "nifty_50_constituents.csv",
            )

            pricing_path = main("2026-11-25", Index.NIFTY_50, base_dir=tmp, max_workers=1)

            self.assertEqual(
                pricing_path,
                Path(tmp) / "pricing" / "2026-11-25_nifty_50_constituents_pricing.csv",
            )
            self.assertTrue(pricing_path.is_file())
            loaded = adapter.read(pricing_path)
            self.assertEqual(loaded.columns, PRICING_COLUMNS)
            self.assertEqual(loaded["symbol"].to_list(), ["HDFCBANK", "RELIANCE"])


if __name__ == "__main__":
    unittest.main()
