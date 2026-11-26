import argparse
import datetime as dt
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import quote

import polars as pl
from curl_cffi.requests import Session as CurlSession

if __package__ in (None, ""):
    _repo_root = Path(__file__).resolve().parents[3]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))

from IO.adapters.csv_adapter import CSVAdapter
from utils.constants import Index

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
DEFAULT_DATA_DIR = Path("data/raw")
YAHOO_CHART_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?period1={period1}&period2={period2}&interval=1d"
)
YAHOO_QUOTE_SUMMARY_URL = (
    "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
    "?modules=assetProfile,summaryDetail,defaultKeyStatistics,financialData,price"
    "&crumb={crumb}"
)
YAHOO_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
YAHOO_COOKIE_WARMUP_URL = "https://fc.yahoo.com"

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

FUNDAMENTAL_COLUMNS = [
    "date",
    "symbol",
    "company_name",
    "sector",
    "industry",
    "currency",
    "market_cap",
    "enterprise_value",
    "shares_outstanding",
    "float_shares",
    "held_percent_insiders",
    "held_percent_institutions",
    "trailing_pe",
    "forward_pe",
    "peg_ratio",
    "price_to_book",
    "price_to_sales_ttm",
    "ev_to_revenue",
    "ev_to_ebitda",
    "trailing_eps",
    "forward_eps",
    "book_value",
    "dividend_rate",
    "dividend_yield",
    "payout_ratio",
    "beta",
    "fifty_two_week_high",
    "fifty_two_week_low",
    "total_revenue",
    "ebitda",
    "net_income_to_common",
    "total_cash",
    "total_debt",
    "debt_to_equity",
    "current_ratio",
    "quick_ratio",
    "return_on_assets",
    "return_on_equity",
    "gross_margins",
    "ebitda_margins",
    "operating_margins",
    "profit_margins",
    "revenue_growth",
    "earnings_growth",
    "free_cashflow",
    "operating_cashflow",
]


def _parse_date(value: str | dt.date | dt.datetime) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        try:
            return dt.date.fromisoformat(cleaned)
        except ValueError as exc:
            raise ValueError(
                f"Invalid date {value!r}; expected YYYY-MM-DD format"
            ) from exc
    raise TypeError(f"Expected str or date, got {type(value).__name__}")


def _index_slug(index_name: str | Index) -> str:
    raw_name = index_name.value if isinstance(index_name, Index) else str(index_name)
    parts = raw_name.strip().lower().replace("_", " ").split()
    if not parts:
        raise ValueError("index_name must be a non-empty NSE index name")
    return "_".join(parts)


def _round_price(value: Any) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def _extract_raw(module: dict[str, Any], key: str) -> Any:
    val = module.get(key)
    if isinstance(val, dict):
        return val.get("raw")
    return val


def _first_present(*values: Any) -> Any:
    for val in values:
        if val is not None:
            return val
    return None


def _to_yahoo_symbol(symbol: str) -> str:
    return quote(f"{symbol}.NS", safe="")


def _get_json_with_retry(
    session: CurlSession,
    url: str,
    *,
    max_attempts: int = 3,
    timeout: int = 15,
) -> dict[str, Any] | None:
    for attempt in range(1, max_attempts + 1):
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_attempts:
            time.sleep(0.5 * attempt)
            continue
        return None
    return None


def _create_yahoo_auth() -> tuple[dict[str, str], str]:
    session = CurlSession(impersonate="chrome124")
    session.get(YAHOO_COOKIE_WARMUP_URL, timeout=15)
    crumb_resp = session.get(YAHOO_CRUMB_URL, timeout=15)
    if crumb_resp.status_code != 200 or not crumb_resp.text.strip():
        raise RuntimeError(
            f"Failed to acquire Yahoo Finance crumb (HTTP {crumb_resp.status_code})"
        )
    cookies = {name: value for name, value in session.cookies.items()}
    return cookies, crumb_resp.text.strip()


def _build_thread_session_getter(cookies: dict[str, str] | None = None):
    local = threading.local()

    def _get_session() -> CurlSession:
        session = getattr(local, "session", None)
        if session is None:
            session = CurlSession(impersonate="chrome124")
            if cookies:
                for name, value in cookies.items():
                    session.cookies.set(name, value, domain=".yahoo.com")
            local.session = session
        return session

    return _get_session


def load_constituent_symbols(
    index_name: str | Index,
    *,
    base_dir: str | Path = DEFAULT_DATA_DIR,
    csv_adapter: CSVAdapter | None = None,
) -> list[str]:
    """Read constituent stock symbols for ``index_name`` from ``data/raw/<index>_constituents.csv``."""
    slug = _index_slug(index_name)
    constituents_path = Path(base_dir) / f"{slug}_constituents.csv"
    adapter = csv_adapter or CSVAdapter()
    df = adapter.read(constituents_path)

    if "symbol" not in df.columns:
        raise ValueError(
            f"Expected 'symbol' column in {constituents_path}, found {df.columns}"
        )

    seen: set[str] = set()
    symbols: list[str] = []
    for raw_sym in df["symbol"].to_list():
        if raw_sym is None:
            continue
        sym = str(raw_sym).strip()
        if sym and sym not in seen:
            seen.add(sym)
            symbols.append(sym)

    if not symbols:
        raise ValueError(f"No symbols found in {constituents_path}")
    return symbols


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
        symbol=_to_yahoo_symbol(symbol),
        period1=period1,
        period2=period2,
    )
    payload = _get_json_with_retry(session, url)
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
                "open": _round_price((quote_data.get("open") or [None])[idx]),
                "high": _round_price((quote_data.get("high") or [None])[idx]),
                "low": _round_price((quote_data.get("low") or [None])[idx]),
                "close": _round_price((quote_data.get("close") or [None])[idx]),
                "adjusted_close": _round_price(
                    adj_closes[idx] if idx < len(adj_closes) else None
                ),
                "volume": int(vol) if vol is not None else None,
            }

    return empty_row


def _fetch_symbol_fundamental(
    session: CurlSession,
    symbol: str,
    target_date: dt.date,
    crumb: str,
) -> dict[str, Any]:
    target_str = target_date.isoformat()
    row: dict[str, Any] = {col: None for col in FUNDAMENTAL_COLUMNS}
    row["date"] = target_str
    row["symbol"] = symbol

    url = YAHOO_QUOTE_SUMMARY_URL.format(
        symbol=_to_yahoo_symbol(symbol),
        crumb=quote(crumb, safe=""),
    )
    payload = _get_json_with_retry(session, url)
    if not payload:
        return row

    results = (payload.get("quoteSummary") or {}).get("result") or []
    if not results:
        return row

    modules = results[0]
    profile = modules.get("assetProfile") or {}
    summary = modules.get("summaryDetail") or {}
    stats = modules.get("defaultKeyStatistics") or {}
    fin = modules.get("financialData") or {}
    price = modules.get("price") or {}

    row.update(
        {
            "company_name": _first_present(price.get("longName"), price.get("shortName")),
            "sector": profile.get("sector"),
            "industry": profile.get("industry"),
            "currency": _first_present(price.get("currency"), summary.get("currency")),
            "market_cap": _first_present(
                _extract_raw(summary, "marketCap"),
                _extract_raw(price, "marketCap"),
            ),
            "enterprise_value": _extract_raw(stats, "enterpriseValue"),
            "shares_outstanding": _extract_raw(stats, "sharesOutstanding"),
            "float_shares": _extract_raw(stats, "floatShares"),
            "held_percent_insiders": _extract_raw(stats, "heldPercentInsiders"),
            "held_percent_institutions": _extract_raw(stats, "heldPercentInstitutions"),
            "trailing_pe": _extract_raw(summary, "trailingPE"),
            "forward_pe": _first_present(
                _extract_raw(summary, "forwardPE"),
                _extract_raw(stats, "forwardPE"),
            ),
            "peg_ratio": _extract_raw(stats, "pegRatio"),
            "price_to_book": _extract_raw(stats, "priceToBook"),
            "price_to_sales_ttm": _extract_raw(summary, "priceToSalesTrailing12Months"),
            "ev_to_revenue": _extract_raw(stats, "enterpriseToRevenue"),
            "ev_to_ebitda": _extract_raw(stats, "enterpriseToEbitda"),
            "trailing_eps": _extract_raw(stats, "trailingEps"),
            "forward_eps": _extract_raw(stats, "forwardEps"),
            "book_value": _extract_raw(stats, "bookValue"),
            "dividend_rate": _extract_raw(summary, "dividendRate"),
            "dividend_yield": _extract_raw(summary, "dividendYield"),
            "payout_ratio": _extract_raw(summary, "payoutRatio"),
            "beta": _first_present(
                _extract_raw(summary, "beta"),
                _extract_raw(stats, "beta"),
            ),
            "fifty_two_week_high": _extract_raw(summary, "fiftyTwoWeekHigh"),
            "fifty_two_week_low": _extract_raw(summary, "fiftyTwoWeekLow"),
            "total_revenue": _extract_raw(fin, "totalRevenue"),
            "ebitda": _extract_raw(fin, "ebitda"),
            "net_income_to_common": _extract_raw(stats, "netIncomeToCommon"),
            "total_cash": _extract_raw(fin, "totalCash"),
            "total_debt": _extract_raw(fin, "totalDebt"),
            "debt_to_equity": _extract_raw(fin, "debtToEquity"),
            "current_ratio": _extract_raw(fin, "currentRatio"),
            "quick_ratio": _extract_raw(fin, "quickRatio"),
            "return_on_assets": _extract_raw(fin, "returnOnAssets"),
            "return_on_equity": _extract_raw(fin, "returnOnEquity"),
            "gross_margins": _extract_raw(fin, "grossMargins"),
            "ebitda_margins": _extract_raw(fin, "ebitdaMargins"),
            "operating_margins": _extract_raw(fin, "operatingMargins"),
            "profit_margins": _first_present(
                _extract_raw(fin, "profitMargins"),
                _extract_raw(stats, "profitMargins"),
            ),
            "revenue_growth": _extract_raw(fin, "revenueGrowth"),
            "earnings_growth": _extract_raw(fin, "earningsGrowth"),
            "free_cashflow": _extract_raw(fin, "freeCashflow"),
            "operating_cashflow": _extract_raw(fin, "operatingCashflow"),
        }
    )
    return row


def fetch_pricing_data(
    symbols: list[str],
    date: str | dt.date | dt.datetime,
    *,
    max_workers: int = 8,
) -> pl.DataFrame:
    """Fetch OHLC, adjusted_close, and volume for ``symbols`` on ``date``."""
    target_date = _parse_date(date)
    start_utc = dt.datetime(
        target_date.year, target_date.month, target_date.day, tzinfo=dt.timezone.utc
    ) - dt.timedelta(days=1)
    period1 = int(start_utc.timestamp())
    period2 = int((start_utc + dt.timedelta(days=3)).timestamp())

    get_session = _build_thread_session_getter()

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


def fetch_fundamental_data(
    symbols: list[str],
    date: str | dt.date | dt.datetime,
    *,
    max_workers: int = 8,
) -> pl.DataFrame:
    """Fetch fundamental snapshot metrics for ``symbols`` tagged with ``date``."""
    target_date = _parse_date(date)
    cookies, crumb = _create_yahoo_auth()
    get_session = _build_thread_session_getter(cookies)

    def _task(sym: str) -> dict[str, Any]:
        return _fetch_symbol_fundamental(get_session(), sym, target_date, crumb)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        rows = list(executor.map(_task, symbols))

    return pl.DataFrame(rows, infer_schema_length=None).select(FUNDAMENTAL_COLUMNS)


def main(
    date: str | dt.date | dt.datetime,
    index_name: str | Index = Index.NIFTY_50,
    *,
    base_dir: str | Path = DEFAULT_DATA_DIR,
    max_workers: int = 8,
) -> tuple[Path, Path]:
    """Read index constituent symbols and save pricing and fundamental CSVs."""
    target_date = _parse_date(date)
    slug = _index_slug(index_name)
    date_prefix = target_date.isoformat()

    adapter = CSVAdapter()
    symbols = load_constituent_symbols(
        index_name,
        base_dir=base_dir,
        csv_adapter=adapter,
    )

    pricing_df = fetch_pricing_data(symbols, target_date, max_workers=max_workers)
    fundamental_df = fetch_fundamental_data(symbols, target_date, max_workers=max_workers)

    root = Path(base_dir)
    pricing_path = root / "pricing" / f"{date_prefix}_{slug}_constituents_pricing.csv"
    fundamental_path = (
        root / "fundamental" / f"{date_prefix}_{slug}_constituents_fundamental.csv"
    )

    written_pricing = adapter.write(pricing_df, pricing_path)
    written_fundamental = adapter.write(fundamental_df, fundamental_path)
    return written_pricing, written_fundamental


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch pricing (OHLC, adjusted_close, volume) and fundamental data for index constituents."
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
    pricing_csv, fundamental_csv = main(
        date=args.date,
        index_name=args.index,
        base_dir=args.base_dir,
    )
    print(f"Wrote pricing CSV to {pricing_csv}")
    print(f"Wrote fundamental CSV to {fundamental_csv}")
