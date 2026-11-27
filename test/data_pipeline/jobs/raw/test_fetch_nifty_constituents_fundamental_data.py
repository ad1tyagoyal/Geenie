import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl

from data_pipeline.jobs.raw.fetch_nifty_constituents_fundamental_data import (
    FUNDAMENTAL_COLUMNS,
    main,
)
from IO.adapters.csv_adapter import CSVAdapter
from utils.constants import Index


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
                    "price": {
                        "longName": name,
                        "currency": "INR",
                        "marketCap": {"raw": mcap},
                    },
                }
            ]
        }
    }


class TestFetchNiftyConstituentsFundamentalData(unittest.TestCase):
    @patch(
        "data_pipeline.jobs.raw.fetch_nifty_constituents_fundamental_data.get_json_with_retry"
    )
    @patch(
        "data_pipeline.jobs.raw.fetch_nifty_constituents_fundamental_data.build_thread_session_getter"
    )
    @patch(
        "data_pipeline.jobs.raw.fetch_nifty_constituents_fundamental_data.create_yahoo_auth"
    )
    def test_main_writes_fundamental_csv(
        self, mock_auth, mock_session_getter, mock_get_json
    ) -> None:
        mock_auth.return_value = ({"B": "cookie"}, "test_crumb")
        mock_session_getter.return_value = lambda: MagicMock()
        mock_get_json.side_effect = [
            _fake_quote_summary(
                "HDFC Bank Limited", "Financial Services", 16.3, 13282348715807
            ),
            _fake_quote_summary(
                "Reliance Industries Limited", "Energy", 22.98, 18872386191360
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            adapter = CSVAdapter()
            adapter.write(
                pl.DataFrame({"symbol": ["HDFCBANK", "RELIANCE"]}),
                Path(tmp) / "nifty_50_constituents.csv",
            )

            fundamental_path = main(
                "2026-11-25",
                Index.NIFTY_50,
                base_dir=tmp,
                max_workers=1,
            )

            self.assertEqual(
                fundamental_path,
                Path(tmp)
                / "fundamental"
                / "2026-11-25_nifty_50_constituents_fundamental.csv",
            )
            self.assertTrue(fundamental_path.is_file())
            loaded = adapter.read(fundamental_path)
            self.assertEqual(loaded.columns, FUNDAMENTAL_COLUMNS)
            self.assertEqual(loaded["symbol"].to_list(), ["HDFCBANK", "RELIANCE"])
            self.assertEqual(loaded["trailing_pe"].to_list(), [16.3, 22.98])


if __name__ == "__main__":
    unittest.main()
