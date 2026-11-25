import tempfile
import unittest
from pathlib import Path

import polars as pl

from IO.adapters.csv_adapter import CSVAdapter


class TestCSVAdapter(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = CSVAdapter()
        self.df = pl.DataFrame({"symbol": ["INFY", "TCS"], "price": [1500.5, 3800.0]})

    def test_write_and_read_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "nested" / "stocks.csv"
            written = self.adapter.write(self.df, out_path)
            self.assertEqual(written, out_path)
            self.assertTrue(out_path.is_file())

            loaded = self.adapter.read(out_path)
            self.assertTrue(loaded.equals(self.df))

    def test_read_missing_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                self.adapter.read(Path(tmp) / "missing.csv")

    def test_write_invalid_type_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(TypeError):
                self.adapter.write({"a": [1]}, Path(tmp) / "out.csv")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
