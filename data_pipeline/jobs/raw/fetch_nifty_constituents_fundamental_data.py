import argparse
import datetime as dt
import sys
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
from utils.helpers import (
    DEFAULT_DATA_DIR,
    IST,
    build_thread_session_getter,
    create_yahoo_auth,
    extract_raw,
    first_present,
    get_json_with_retry,
    index_slug,
    load_constituent_symbols,
    parse_date,
    to_yahoo_symbol,
)

YAHOO_QUOTE_SUMMARY_URL = (
    "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
    "?modules=assetProfile,summaryDetail,defaultKeyStatistics,financialData,price"
    "&crumb={crumb}"
)

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
        symbol=to_yahoo_symbol(symbol),
        crumb=quote(crumb, safe=""),
    )
    payload = get_json_with_retry(session, url)
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
            "company_name": first_present(price.get("longName"), price.get("shortName")),
            "sector": profile.get("sector"),
            "industry": profile.get("industry"),
            "currency": first_present(price.get("currency"), summary.get("currency")),
            "market_cap": first_present(
                extract_raw(summary, "marketCap"),
                extract_raw(price, "marketCap"),
            ),
            "enterprise_value": extract_raw(stats, "enterpriseValue"),
            "shares_outstanding": extract_raw(stats, "sharesOutstanding"),
            "float_shares": extract_raw(stats, "floatShares"),
            "held_percent_insiders": extract_raw(stats, "heldPercentInsiders"),
            "held_percent_institutions": extract_raw(stats, "heldPercentInstitutions"),
            "trailing_pe": extract_raw(summary, "trailingPE"),
            "forward_pe": first_present(
                extract_raw(summary, "forwardPE"),
                extract_raw(stats, "forwardPE"),
            ),
            "peg_ratio": extract_raw(stats, "pegRatio"),
            "price_to_book": extract_raw(stats, "priceToBook"),
            "price_to_sales_ttm": extract_raw(summary, "priceToSalesTrailing12Months"),
            "ev_to_revenue": extract_raw(stats, "enterpriseToRevenue"),
            "ev_to_ebitda": extract_raw(stats, "enterpriseToEbitda"),
            "trailing_eps": extract_raw(stats, "trailingEps"),
            "forward_eps": extract_raw(stats, "forwardEps"),
            "book_value": extract_raw(stats, "bookValue"),
            "dividend_rate": extract_raw(summary, "dividendRate"),
            "dividend_yield": extract_raw(summary, "dividendYield"),
            "payout_ratio": extract_raw(summary, "payoutRatio"),
            "beta": first_present(
                extract_raw(summary, "beta"),
                extract_raw(stats, "beta"),
            ),
            "fifty_two_week_high": extract_raw(summary, "fiftyTwoWeekHigh"),
            "fifty_two_week_low": extract_raw(summary, "fiftyTwoWeekLow"),
            "total_revenue": extract_raw(fin, "totalRevenue"),
            "ebitda": extract_raw(fin, "ebitda"),
            "net_income_to_common": extract_raw(stats, "netIncomeToCommon"),
            "total_cash": extract_raw(fin, "totalCash"),
            "total_debt": extract_raw(fin, "totalDebt"),
            "debt_to_equity": extract_raw(fin, "debtToEquity"),
            "current_ratio": extract_raw(fin, "currentRatio"),
            "quick_ratio": extract_raw(fin, "quickRatio"),
            "return_on_assets": extract_raw(fin, "returnOnAssets"),
            "return_on_equity": extract_raw(fin, "returnOnEquity"),
            "gross_margins": extract_raw(fin, "grossMargins"),
            "ebitda_margins": extract_raw(fin, "ebitdaMargins"),
            "operating_margins": extract_raw(fin, "operatingMargins"),
            "profit_margins": first_present(
                extract_raw(fin, "profitMargins"),
                extract_raw(stats, "profitMargins"),
            ),
            "revenue_growth": extract_raw(fin, "revenueGrowth"),
            "earnings_growth": extract_raw(fin, "earningsGrowth"),
            "free_cashflow": extract_raw(fin, "freeCashflow"),
            "operating_cashflow": extract_raw(fin, "operatingCashflow"),
        }
    )
    return row


def fetch_fundamental_data(
    symbols: list[str],
    date: str | dt.date | dt.datetime,
    *,
    max_workers: int = 8,
) -> pl.DataFrame:
    """Fetch fundamental snapshot metrics for ``symbols`` tagged with ``date``."""
    target_date = parse_date(date)
    cookies, crumb = create_yahoo_auth()
    get_session = build_thread_session_getter(cookies)

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
) -> Path:
    """Read index constituent symbols and write fundamental snapshot CSV."""
    target_date = parse_date(date)
    slug = index_slug(index_name)
    date_prefix = target_date.isoformat()

    adapter = CSVAdapter()
    symbols = load_constituent_symbols(
        index_name,
        base_dir=base_dir,
        csv_adapter=adapter,
    )

    fundamental_df = fetch_fundamental_data(symbols, target_date, max_workers=max_workers)
    fundamental_path = (
        Path(base_dir)
        / "fundamental"
        / f"{date_prefix}_{slug}_constituents_fundamental.csv"
    )
    return adapter.write(fundamental_df, fundamental_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch fundamental snapshot data for index constituents."
    )
    parser.add_argument(
        "--date",
        default=dt.datetime.now(IST).date().isoformat(),
        help="Snapshot date tag in YYYY-MM-DD format (default: today IST).",
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
    fundamental_csv = main(
        date=args.date,
        index_name=args.index,
        base_dir=args.base_dir,
    )
    print(f"Wrote fundamental CSV to {fundamental_csv}")
