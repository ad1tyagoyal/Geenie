import datetime as dt
import tempfile
import unittest
from pathlib import Path

import polars as pl

from IO.adapters.csv_adapter import CSVAdapter
from utils.constants import Index
from utils.helpers import (
    extract_raw,
    first_present,
    index_slug,
    load_constituent_symbols,
    normalize_index_name,
    parse_date,
    round_price,
    to_yahoo_symbol,
)


class TestHelpers(unittest.TestCase):
    def test_parse_date_accepts_str_date_datetime(self) -> None:
        self.assertEqual(parse_date("2026-11-25"), dt.date(2026, 11, 25))
        self.assertEqual(parse_date(dt.date(2026, 11, 25)), dt.date(2026, 11, 25))
        self.assertEqual(
            parse_date(dt.datetime(2026, 11, 25, 14, 0)),
            dt.date(2026, 11, 25),
        )

    def test_parse_date_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_date("25-11-2026")
        with self.assertRaises(TypeError):
            parse_date(20261125)  # type: ignore[arg-type]

    def test_index_normalization_and_slug(self) -> None:
        self.assertEqual(normalize_index_name(" nifty_50 "), "NIFTY 50")
        self.assertEqual(index_slug(Index.NIFTY_50), "nifty_50")
        self.assertEqual(index_slug("  NIFTY 100 "), "nifty_100")

    def test_scalar_and_symbol_helpers(self) -> None:
        self.assertEqual(round_price(846.2000122), 846.2)
        self.assertIsNone(round_price(None))
        self.assertEqual(extract_raw({"pe": {"raw": 18.5}}, "pe"), 18.5)
        self.assertIsNone(extract_raw({}, "pe"))
        self.assertEqual(first_present(None, 0, 5), 0)
        self.assertEqual(to_yahoo_symbol("M&M"), "M%26M.NS")

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


if __name__ == "__main__":
    unittest.main()
