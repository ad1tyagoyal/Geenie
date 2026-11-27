import argparse
import datetime as dt
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import polars as pl
from curl_cffi.requests import Session as CurlSession

if __package__ in (None, ""):
    _repo_root = Path(__file__).resolve().parents[3]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

from IO.adapters.csv_adapter import CSVAdapter
from utils.constants import Index
from utils.helpers import (
    DEFAULT_DATA_DIR,
    IST,
    build_thread_session_getter,
    get_json_with_retry,
    index_slug,
    load_constituent_symbols,
    parse_date,
    round_price,
    to_yahoo_symbol,
)

YAHOO_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?period1={period1}&period2={period2}&interval=1d"
)

PRICING_COLUMNS = [
    "date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "adjusted_close",
    "volume",
]


def _fetch_symbol_pricing(
    session: CurlSession,
    symbol: str,
    target_date: dt.date,
    period1: int,
    period2: int,
) -> dict[str, Any]:
    target_str = target_date.isoformat()
    empty_row = {col: None for col in PRICING_COLUMNS}
    empty_row["date"] = target_str
    empty_row["symbol"] = symbol

    url = YAHOO_CHART_URL.format(
        symbol=to_yahoo_symbol(symbol),
        period1=period1,
        period2=period2,
    )
    payload = get_json_with_retry(session, url)
    if not payload:
        return empty_row

    results = (payload.get("chart") or {}).get("result") or []
    if not results:
        return empty_row

    chart = results[0]
    timestamps = chart.get("timestamp") or []
    indicators = chart.get("indicators") or {}
    quote_list = indicators.get("quote") or []
    adj_list = indicators.get("adjclose") or []
    if not timestamps or not quote_list:
        return empty_row

    quote_data = quote_list[0]
    adj_closes = adj_list[0].get("adjclose", []) if adj_list else []

    for idx, ts in enumerate(timestamps):
        bar_date = dt.datetime.fromtimestamp(ts, IST).date()
        if bar_date == target_date:
            vol = (quote_data.get("volume") or [None])[idx]
            return {
                "date": target_str,
                "symbol": symbol,
                "open": round_price((quote_data.get("open") or [None])[idx]),
                "high": round_price((quote_data.get("high") or [None])[idx]),
                "low": round_price((quote_data.get("low") or [None])[idx]),
                "close": round_price((quote_data.get("close") or [None])[idx]),
                "adjusted_close": round_price(
                    adj_closes[idx] if idx < len(adj_closes) else None
                ),
                "volume": int(vol) if vol is not None else None,
            }

    return empty_row


def fetch_pricing_data(
    symbols: list[str],
    date: str | dt.date | dt.datetime,
    *,
    max_workers: int = 8,
) -> pl.DataFrame:
    """Fetch OHLC, adjusted_close, and volume for ``symbols`` on ``date``."""
    target_date = parse_date(date)
    start_utc = dt.datetime(
        target_date.year, target_date.month, target_date.day, tzinfo=dt.timezone.utc
    ) - dt.timedelta(days=1)
    period1 = int(start_utc.timestamp())
    period2 = int((start_utc + dt.timedelta(days=3)).timestamp())

    get_session = build_thread_session_getter()

    def _task(sym: str) -> dict[str, Any]:
        return _fetch_symbol_pricing(get_session(), sym, target_date, period1, period2)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        rows = list(executor.map(_task, symbols))

    if not any(row["close"] is not None for row in rows):
        raise ValueError(
            f"No pricing data available for {target_date.isoformat()} "
            "(market may have been closed on this date)"
        )

    return pl.DataFrame(rows, infer_schema_length=None).select(PRICING_COLUMNS)


def main(
    date: str | dt.date | dt.datetime,
    index_name: str | Index = Index.NIFTY_50,
    *,
    base_dir: str | Path = DEFAULT_DATA_DIR,
    max_workers: int = 8,
) -> Path:
    """Read index constituent symbols and write daily OHLCV pricing CSV."""
    target_date = parse_date(date)
    slug = index_slug(index_name)
    date_prefix = target_date.isoformat()

    adapter = CSVAdapter()
    symbols = load_constituent_symbols(
        index_name,
        base_dir=base_dir,
        csv_adapter=adapter,
    )

    pricing_df = fetch_pricing_data(symbols, target_date, max_workers=max_workers)
    pricing_path = Path(base_dir) / "pricing" / f"{date_prefix}_{slug}_constituents_pricing.csv"
    return adapter.write(pricing_df, pricing_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch daily pricing (OHLC, adjusted_close, volume) for index constituents."
    )
    parser.add_argument(
        "--date",
        default=dt.datetime.now(IST).date().isoformat(),
        help="Target trading date in YYYY-MM-DD format (default: today IST).",
    )
    parser.add_argument(
        "--index",
        default=Index.NIFTY_50.value,
        help="NSE index name (default: 'NIFTY 50').",
    )
    parser.add_argument(
        "--base-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Base raw data directory (default: data/raw).",
    )
    args = parser.parse_args()
    pricing_csv = main(
        date=args.date,
        index_name=args.index,
        base_dir=args.base_dir,
    )
    print(f"Wrote pricing CSV to {pricing_csv}")
