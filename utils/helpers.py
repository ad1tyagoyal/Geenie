import datetime as dt
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from curl_cffi.requests import Session as CurlSession

from IO.adapters.csv_adapter import CSVAdapter
from utils.constants import Index

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
DEFAULT_DATA_DIR = Path("data/raw")
YAHOO_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
YAHOO_COOKIE_WARMUP_URL = "https://fc.yahoo.com"


def parse_date(value: str | dt.date | dt.datetime) -> dt.date:
    """Parse a date string (YYYY-MM-DD), date, or datetime into a ``datetime.date``."""
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


def normalize_index_name(index_name: str | Index) -> str:
    """Return the uppercase, whitespace-trimmed NSE index name."""
    raw_name = index_name.value if isinstance(index_name, Index) else str(index_name)
    normalized = " ".join(raw_name.strip().replace("_", " ").upper().split())
    if not normalized:
        raise ValueError("index_name must be a non-empty NSE index name")
    return normalized


def index_slug(index_name: str | Index) -> str:
    """Return the lowercase underscore-separated file slug for ``index_name``."""
    return normalize_index_name(index_name).lower().replace(" ", "_")


def round_price(value: Any) -> float | None:
    """Round numeric prices to 4 decimals to remove float32 transport noise."""
    if value is None:
        return None
    return round(float(value), 4)


def extract_raw(module: dict[str, Any], key: str) -> Any:
    """Extract the scalar ``raw`` field from a Yahoo Finance quoteSummary value."""
    val = module.get(key)
    if isinstance(val, dict):
        return val.get("raw")
    return val


def first_present(*values: Any) -> Any:
    """Return the first argument that is not ``None``."""
    for val in values:
        if val is not None:
            return val
    return None


def to_yahoo_symbol(symbol: str) -> str:
    """Format and URL-encode an NSE equity symbol for Yahoo Finance (``<SYMBOL>.NS``)."""
    return quote(f"{symbol}.NS", safe="")


def get_json_with_retry(
    session: CurlSession,
    url: str,
    *,
    max_attempts: int = 3,
    timeout: int = 15,
) -> dict[str, Any] | None:
    """Fetch a JSON response with bounded retry/backoff on transient HTTP errors."""
    for attempt in range(1, max_attempts + 1):
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_attempts:
            time.sleep(0.5 * attempt)
            continue
        return None
    return None


def create_yahoo_auth() -> tuple[dict[str, str], str]:
    """Warm Yahoo Finance cookies and fetch a crumb token for quoteSummary calls."""
    session = CurlSession(impersonate="chrome124")
    session.get(YAHOO_COOKIE_WARMUP_URL, timeout=15)
    crumb_resp = session.get(YAHOO_CRUMB_URL, timeout=15)
    if crumb_resp.status_code != 200 or not crumb_resp.text.strip():
        raise RuntimeError(
            f"Failed to acquire Yahoo Finance crumb (HTTP {crumb_resp.status_code})"
        )
    cookies = {name: value for name, value in session.cookies.items()}
    return cookies, crumb_resp.text.strip()


def build_thread_session_getter(cookies: dict[str, str] | None = None):
    """Return a thread-local ``CurlSession`` factory seeded with optional Yahoo cookies."""
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
    """Read deduplicated constituent stock symbols from ``<base_dir>/<index>_constituents.csv``."""
    slug = index_slug(index_name)
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
