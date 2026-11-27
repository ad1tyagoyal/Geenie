import argparse
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import polars as pl
from nsepython import nsefetch

if __package__ in (None, ""):
    _repo_root = Path(__file__).resolve().parents[3]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

from IO.adapters.csv_adapter import CSVAdapter
from utils.constants import Index
from utils.helpers import DEFAULT_DATA_DIR, index_slug, normalize_index_name

NSE_INDEX_CONSTITUENTS_URL = (
    "https://www.nseindia.com/api/NextApi/apiClient/marketWatchApi"
    "?functionName=getIndicesData&symbol={symbol}"
)


def _extract_constituent_rows(
    payload: Any,
    normalized_index: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError(f"Expected dict payload from nsefetch, got {type(payload).__name__}")

    data_container = payload.get("data")
    if not isinstance(data_container, dict):
        return []

    rows = data_container.get("data")
    if not isinstance(rows, list):
        return []

    return [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("priority") != 1
        and row.get("symbol") != normalized_index
    ]


def fetch_nifty_constituents(index_name: str | Index) -> pl.DataFrame:
    """Fetch all constituent stocks for an NSE index as a Polars DataFrame.

    Args:
        index_name: NSE index name (for example ``"NIFTY 50"`` or ``Index.NIFTY_50``).

    Returns:
        A Polars DataFrame containing the constituent stocks for the index.

    Raises:
        ValueError: If ``index_name`` is empty or NSE returns no constituents.
    """
    normalized_index = normalize_index_name(index_name)
    url = NSE_INDEX_CONSTITUENTS_URL.format(symbol=quote(normalized_index))
    payload = nsefetch(url)

    rows = _extract_constituent_rows(payload, normalized_index)
    if not rows:
        raise ValueError(f"No constituent stocks returned for index: {normalized_index}")

    return pl.DataFrame(rows, infer_schema_length=None)


def _default_output_path(index_name: str | Index) -> Path:
    return DEFAULT_DATA_DIR / f"{index_slug(index_name)}_constituents.csv"


def main(
    index_name: str | Index = Index.NIFTY_50,
    output_path: str | Path | None = None,
) -> Path:
    """Fetch index constituents into a Polars DataFrame and write them to CSV."""
    df: pl.DataFrame = fetch_nifty_constituents(index_name)
    target_path = Path(output_path) if output_path is not None else _default_output_path(index_name)
    return CSVAdapter().write(df, target_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch NSE index constituents to CSV.")
    parser.add_argument(
        "--index",
        default=Index.NIFTY_50.value,
        help="NSE index name (default: 'NIFTY 50').",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional destination CSV path (default: data/raw/<index>_constituents.csv).",
    )
    args = parser.parse_args()
    written_path = main(index_name=args.index, output_path=args.output)
    print(f"Wrote constituents CSV to {written_path}")
