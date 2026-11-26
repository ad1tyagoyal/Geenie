import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl

from data_pipeline.jobs.raw.fetch_nifty_constituents_data import (
    FUNDAMENTAL_COLUMNS,
    PRICING_COLUMNS,
    fetch_fundamental_data,
    fetch_pricing_data,
    load_constituent_symbols,
    main,
)
from IO.adapters.csv_adapter import CSVAdapter
from utils.constants import Index


def _fake_chart_payload(ts: int, o: float, h: float, l: float, c: float, adj: float, vol: int) -> dict:
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


def _fake_quote_summary(name: str, sector: str, pe: float, mcap: int) -> dict:
    return {
        "quoteSummary": {
            "result": [
                {
                    "assetProfile": {"sector": sector, "industry": "Banks - Regional"},
                    "summaryDetail": {
                        "currency": "INR",
                        "marketCap": {"raw": mcap},
                        "trailingPE": {"raw": pe},
                        "forwardPE": {"raw": pe - 1.0},
                        "dividendRate": {"raw": 10.0},
                        "dividendYield": {"raw": 0.01},
                        "payoutRatio": {"raw": 0.2},
                        "beta": {"raw": 0.9},
                        "fiftyTwoWeekHigh": {"raw": 1000.0},
                        "fiftyTwoWeekLow": {"raw": 700.0},
                        "priceToSalesTrailing12Months": {"raw": 3.5},
                    },
                    "defaultKeyStatistics": {
                        "enterpriseValue": {"raw": mcap + 1000},
                        "sharesOutstanding": {"raw": 1000000},
                        "floatShares": {"raw": 800000},
                        "heldPercentInsiders": {"raw": 0.2},
                        "heldPercentInstitutions": {"raw": 0.5},
                        "pegRatio": {"raw": 1.2},
                        "priceToBook": {"raw": 2.4},
                        "enterpriseToRevenue": {"raw": 4.0},
                        "enterpriseToEbitda": {"raw": 12.0},
                        "trailingEps": {"raw": 50.0},
                        "forwardEps": {"raw": 55.0},
                        "bookValue": {"raw": 350.0},
                        "netIncomeToCommon": {"raw": 50000000},
                        "profitMargins": {"raw": 0.18},
                    },
                    "financialData": {
                        "totalRevenue": {"raw": 200000000},
                        "ebitda": {"raw": 60000000},
                        "totalCash": {"raw": 40000000},
                        "totalDebt": {"raw": 10000000},
                        "debtToEquity": {"raw": 15.0},
                        "currentRatio": {"raw": 1.5},
                        "quickRatio": {"raw": 1.2},
                        "returnOnAssets": {"raw": 0.05},
                        "returnOnEquity": {"raw": 0.16},
                        "grossMargins": {"raw": 0.4},
                        "ebitdaMargins": {"raw": 0.3},
                        "operatingMargins": {"raw": 0.25},
                        "profitMargins": {"raw": 0.18},
                        "revenueGrowth": {"raw": 0.12},
                        "earningsGrowth": {"raw": 0.14},
                        "freeCashflow": {"raw": 25000000},
                        "operatingCashflow": {"raw": 35000000},
                    },
                    "price": {"longName": name, "currency": "INR", "marketCap": {"raw": mcap}},
                }
            ]
        }
    }


class TestFetchNiftyConstituentsData(unittest.TestCase):
    def test_load_constituent_symbols_deduplicates_and_strips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = CSVAdapter()
            adapter.write(
                pl.DataFrame({"symbol": [" HDFCBANK ", "RELIANCE", "HDFCBANK", None, ""]}),
                Path(tmp) / "nifty_50_constituents.csv",
            )
            symbols = load_constituent_symbols(Index.NIFTY_50, base_dir=tmp, csv_adapter=adapter)
            self.assertEqual(symbols, ["HDFCBANK", "RELIANCE"])

    def test_load_constituent_symbols_missing_column_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = CSVAdapter()
            adapter.write(
                pl.DataFrame({"ticker": ["HDFCBANK"]}),
                Path(tmp) / "nifty_50_constituents.csv",
            )
            with self.assertRaises(ValueError):
                load_constituent_symbols("NIFTY 50", base_dir=tmp, csv_adapter=adapter)

    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents_data._get_json_with_retry")
    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents_data._build_thread_session_getter")
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

    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents_data._get_json_with_retry")
    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents_data._build_thread_session_getter")
    def test_fetch_pricing_data_raises_when_market_closed(
        self, mock_session_getter, mock_get_json
    ) -> None:
        mock_session_getter.return_value = lambda: MagicMock()
        mock_get_json.return_value = {"chart": {"result": [{"timestamp": [], "indicators": {"quote": [{}]}}]}}

        with self.assertRaises(ValueError):
            fetch_pricing_data(["HDFCBANK"], "2026-11-22", max_workers=1)

    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents_data._get_json_with_retry")
    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents_data._build_thread_session_getter")
    @patch("data_pipeline.jobs.raw.fetch_nifty_constituents_data._create_yahoo_auth")
    def test_fetch_fundamental_data_and_main_outputs(
        self, mock_auth, mock_session_getter, mock_get_json
    ) -> None:
        mock_auth.return_value = ({"B": "cookie"}, "test_crumb")
        mock_session_getter.return_value = lambda: MagicMock()

        ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
        ts = int(dt.datetime(2026, 11, 25, 9, 15, tzinfo=ist).timestamp())
        mock_get_json.side_effect = [
            _fake_chart_payload(ts, 833.1, 850.5, 831.55, 846.2, 846.2, 48187313),
            _fake_chart_payload(ts, 1359.8, 1394.2, 1357.0, 1373.9, 1373.9, 18781717),
            _fake_quote_summary("HDFC Bank Limited", "Financial Services", 16.3, 13282348715807),
            _fake_quote_summary("Reliance Industries Limited", "Energy", 22.98, 18872386191360),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            adapter = CSVAdapter()
            adapter.write(
                pl.DataFrame({"symbol": ["HDFCBANK", "RELIANCE"]}),
                Path(tmp) / "nifty_50_constituents.csv",
            )

            pricing_path, fundamental_path = main(
                "2026-11-25",
                Index.NIFTY_50,
                base_dir=tmp,
                max_workers=1,
            )

            self.assertEqual(
                pricing_path,
                Path(tmp) / "pricing" / "2026-11-25_nifty_50_constituents_pricing.csv",
            )
            self.assertEqual(
                fundamental_path,
                Path(tmp) / "fundamental" / "2026-11-25_nifty_50_constituents_fundamental.csv",
            )
            self.assertTrue(pricing_path.is_file())
            self.assertTrue(fundamental_path.is_file())

            pricing_loaded = adapter.read(pricing_path)
            fundamental_loaded = adapter.read(fundamental_path)
            self.assertEqual(pricing_loaded.columns, PRICING_COLUMNS)
            self.assertEqual(fundamental_loaded.columns, FUNDAMENTAL_COLUMNS)
            self.assertEqual(pricing_loaded["symbol"].to_list(), ["HDFCBANK", "RELIANCE"])
            self.assertEqual(fundamental_loaded["trailing_pe"].to_list(), [16.3, 22.98])


if __name__ == "__main__":
    unittest.main()
