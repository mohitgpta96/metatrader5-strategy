"""
TwelveData API fetcher for COMEX/global commodity futures.
Primary source: TwelveData (higher quality, no rate-limit surprises for commodities).
Fallback source: yfinance (automatic, transparent, per-ticker).

Free tier limits:
  - 800 credits/day
  - 8 credits/minute  →  sleep 8 s between requests (conservative)

Usage:
    from data.fetcher_twelvedata import fetch_comex_all_td, fetch_comex_single_td

    data = fetch_comex_all_td(interval="1h")   # returns {yf_ticker: DataFrame}
    df   = fetch_comex_single_td("GC=F")       # returns DataFrame or None
"""
import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Path setup — allow running as __main__ and as an import
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DATA_CACHE_DIR

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ticker mapping: yfinance format  →  TwelveData symbol
# None means TwelveData does not support this instrument; go straight to yfinance.
# ---------------------------------------------------------------------------
_YF_TO_TD: dict[str, Optional[str]] = {
    "GC=F":  "XAU/USD",    # Gold
    "SI=F":  "XAG/USD",    # Silver
    "CL=F":  "WTI/USD",    # Crude Oil WTI
    "BZ=F":  "BRENT/USD",  # Brent Crude  — may not be on free tier; fallback handled
    "NG=F":  "NG/USD",     # Natural Gas
    "HG=F":  "HG/USD",     # Copper       — may not be on free tier; fallback handled
    "PL=F":  "XPT/USD",    # Platinum     — may not be on free tier; fallback handled
}

# TwelveData interval strings for the intervals we care about
_INTERVAL_MAP: dict[str, str] = {
    "1h":   "1h",
    "1d":   "1day",
    "1day": "1day",
}

# TwelveData REST endpoint
_TD_BASE_URL = "https://api.twelvedata.com/time_series"

# Seconds to sleep between TwelveData requests to stay under 8 req/min
_TD_RATE_LIMIT_SLEEP = 8  # seconds

# Maximum candles to request (5000 = ~208 days of 1 h data)
_TD_OUTPUTSIZE = 5000

# HTTP request timeout in seconds
_REQUEST_TIMEOUT = 30


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    """Read the TwelveData API key from environment. Returns empty string if absent."""
    return os.environ.get("TWELVEDATA_API_KEY", "").strip()


def _cache_path(yf_ticker: str, interval: str) -> Path:
    """Return the CSV cache path for a given ticker and interval (mirrors fetcher.py logic)."""
    safe_name = yf_ticker.replace("=", "_").replace("^", "IDX_").replace(".", "_")
    return DATA_CACHE_DIR / f"{safe_name}_{interval}.csv"


def _save_cache(df: pd.DataFrame, yf_ticker: str, interval: str) -> None:
    """Write DataFrame to CSV cache (same path/format as fetcher.py)."""
    path = _cache_path(yf_ticker, interval)
    try:
        df.to_csv(path)
    except Exception as exc:
        logger.warning("Could not write cache for %s: %s", yf_ticker, exc)


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def _twelvedata_to_df(response_json: dict, ticker: str) -> Optional[pd.DataFrame]:
    """
    Convert a TwelveData JSON response to a pandas DataFrame.

    Expected JSON shape:
        {
            "values": [
                {
                    "datetime": "2024-01-15 09:00:00",
                    "open":  "2050.10",
                    "high":  "2055.30",
                    "low":   "2048.00",
                    "close": "2053.75",
                    "volume": "12345"
                },
                ...
            ],
            "status": "ok"
        }

    Returns a DataFrame with:
        - DatetimeIndex (ascending)
        - Columns: Open, High, Low, Close, Volume  (Title case, float64 / int64)

    Returns None on any structural problem.
    """
    # --- top-level error check ---
    status = response_json.get("status", "")
    if status != "ok":
        code    = response_json.get("code", "?")
        message = response_json.get("message", str(response_json))
        logger.warning(
            "[TD] API error for %s — code=%s message=%s", ticker, code, message
        )
        return None

    values = response_json.get("values")
    if not values or not isinstance(values, list):
        logger.warning("[TD] Empty 'values' in response for %s", ticker)
        return None

    # --- build DataFrame ---
    try:
        df = pd.DataFrame(values)

        # Parse datetime index
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
        df.index.name = "Datetime"

        # TwelveData returns newest-first; reverse to oldest-first (chronological)
        df = df.sort_index(ascending=True)

        # Cast OHLCV columns to numeric
        rename_map = {
            "open":   "Open",
            "high":   "High",
            "low":    "Low",
            "close":  "Close",
            "volume": "Volume",
        }
        df = df.rename(columns=rename_map)

        for col in ("Open", "High", "Low", "Close"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Volume may be absent for some forex/commodity symbols on free tier
        if "Volume" in df.columns:
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype("int64")
        else:
            logger.debug("[TD] No volume data for %s — filling with 0", ticker)
            df["Volume"] = 0

        # Keep only the five standard columns (drop any extras like 'previous_close')
        df = df[["Open", "High", "Low", "Close", "Volume"]]

        # Drop rows where price data is all NaN
        df = df.dropna(subset=["Open", "High", "Low", "Close"], how="all")

        if df.empty:
            logger.warning("[TD] DataFrame is empty after cleaning for %s", ticker)
            return None

        return df

    except Exception as exc:
        logger.error("[TD] DataFrame conversion failed for %s: %s", ticker, exc)
        return None


# ---------------------------------------------------------------------------
# Single-ticker fetch (TwelveData → yfinance fallback)
# ---------------------------------------------------------------------------

def fetch_comex_single_td(yf_ticker: str, interval: str = "1h") -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data for a single COMEX futures ticker.

    Strategy:
        1. If TWELVEDATA_API_KEY is set and a TD symbol mapping exists →
           try TwelveData first.
        2. On any failure (network error, API error, unsupported symbol,
           missing key) → fall back to yfinance transparently.

    Parameters
    ----------
    yf_ticker : str
        Yahoo Finance ticker string, e.g. "GC=F".
    interval : str
        "1h" (default) or "1d".

    Returns
    -------
    pd.DataFrame with columns Open, High, Low, Close, Volume and a DatetimeIndex.
    Returns None if both sources fail.
    """
    td_interval = _INTERVAL_MAP.get(interval, interval)
    api_key     = _get_api_key()
    td_symbol   = _YF_TO_TD.get(yf_ticker)

    # ------------------------------------------------------------------
    # Attempt TwelveData
    # ------------------------------------------------------------------
    if api_key and td_symbol:
        df = _fetch_from_twelvedata(yf_ticker, td_symbol, td_interval, api_key)
        if df is not None:
            _save_cache(df, yf_ticker, interval)
            return df
        logger.info(
            "[TD] TwelveData failed for %s (%s) — falling back to yfinance",
            yf_ticker, td_symbol,
        )
    elif not api_key:
        logger.debug("[TD] TWELVEDATA_API_KEY not set — using yfinance directly for %s", yf_ticker)
    elif not td_symbol:
        logger.debug("[TD] No TwelveData mapping for %s — using yfinance directly", yf_ticker)

    # ------------------------------------------------------------------
    # Fallback: yfinance
    # ------------------------------------------------------------------
    return _fetch_from_yfinance(yf_ticker, interval)


def _fetch_from_twelvedata(
    yf_ticker: str,
    td_symbol: str,
    td_interval: str,
    api_key: str,
) -> Optional[pd.DataFrame]:
    """
    Make one TwelveData REST call and return a cleaned DataFrame.
    Returns None on any error so the caller can fall back gracefully.
    """
    params = {
        "symbol":     td_symbol,
        "interval":   td_interval,
        "outputsize": _TD_OUTPUTSIZE,
        "apikey":     api_key,
        "format":     "JSON",
    }

    try:
        logger.debug("[TD] Requesting %s interval=%s", td_symbol, td_interval)
        resp = requests.get(
            _TD_BASE_URL,
            params=params,
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        logger.warning("[TD] Request timed out for %s (%s)", yf_ticker, td_symbol)
        return None
    except requests.exceptions.HTTPError as exc:
        logger.warning("[TD] HTTP error for %s: %s", yf_ticker, exc)
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning("[TD] Network error for %s: %s", yf_ticker, exc)
        return None
    except ValueError as exc:
        logger.warning("[TD] JSON decode error for %s: %s", yf_ticker, exc)
        return None

    return _twelvedata_to_df(data, yf_ticker)


def _fetch_from_yfinance(yf_ticker: str, interval: str = "1h") -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data via yfinance and return a cleaned DataFrame.
    This mirrors the logic in data/fetcher.py: fetch_single().
    """
    import yfinance as yf

    # Choose a sensible period based on interval
    if interval in ("1m", "5m", "15m", "30m", "1h"):
        period = "60d"
    else:
        period = "1y"

    try:
        df = yf.download(
            yf_ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
        if df is None or df.empty:
            logger.warning("[YF] No data returned for %s", yf_ticker)
            return None

        # Flatten MultiIndex columns if present (yfinance >= 0.2)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Standardise column names to Title case
        df.columns = [c.title() for c in df.columns]

        # Keep only the five standard columns
        available = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
        df = df[available].copy()

        # Ensure Volume column exists
        if "Volume" not in df.columns:
            df["Volume"] = 0

        df = df.dropna(subset=["Open", "High", "Low", "Close"], how="all")
        if df.empty:
            logger.warning("[YF] DataFrame empty after cleaning for %s", yf_ticker)
            return None

        _save_cache(df, yf_ticker, interval)
        logger.debug("[YF] Fetched %d rows for %s via yfinance", len(df), yf_ticker)
        return df

    except Exception as exc:
        logger.error("[YF] Failed to fetch %s: %s", yf_ticker, exc)
        return None


# ---------------------------------------------------------------------------
# Batch fetch for all 7 COMEX tickers
# ---------------------------------------------------------------------------

def fetch_comex_all_td(interval: str = "1h") -> dict[str, pd.DataFrame]:
    """
    Fetch OHLCV data for all supported COMEX futures tickers.

    For each ticker the function tries TwelveData first, then falls back to
    yfinance automatically.  A rate-limit sleep of 8 seconds is inserted
    between each TwelveData request to stay within the free-tier limit of
    8 calls/minute.

    Parameters
    ----------
    interval : str
        "1h" (default) or "1d".

    Returns
    -------
    dict mapping yfinance ticker → pd.DataFrame.
    Only successfully fetched tickers are included.
    """
    results: dict[str, pd.DataFrame] = {}
    api_key      = _get_api_key()
    td_interval  = _INTERVAL_MAP.get(interval, interval)

    for i, yf_ticker in enumerate(_YF_TO_TD):
        td_symbol = _YF_TO_TD[yf_ticker]
        print(f"  [TD] Fetching {yf_ticker} ({td_symbol or 'yfinance only'})...")

        # Rate-limit sleep: apply between TwelveData requests, not on yfinance fallback
        # Skip sleep on the very first request.
        if i > 0 and api_key and td_symbol:
            logger.debug("[TD] Rate-limit sleep %ds before next request", _TD_RATE_LIMIT_SLEEP)
            time.sleep(_TD_RATE_LIMIT_SLEEP)

        df = fetch_comex_single_td(yf_ticker, interval=interval)

        if df is not None:
            results[yf_ticker] = df
            print(f"      OK — {len(df)} candles")
        else:
            print(f"      FAILED — {yf_ticker} skipped")

    print(
        f"\n  [TD] Done — {len(results)}/{len(_YF_TO_TD)} tickers fetched successfully"
    )
    return results


# ---------------------------------------------------------------------------
# NSE Stock support
# ---------------------------------------------------------------------------

def _yf_to_td_nse(yf_ticker: str):
    """Convert yfinance NSE ticker to TwelveData symbol.
    RELIANCE.NS  →  RELIANCE:NSE
    M&M.NS       →  M&M:NSE
    """
    if not yf_ticker.endswith(".NS"):
        return None
    symbol = yf_ticker[:-3]   # strip .NS
    return f"{symbol}:NSE"


def fetch_stock_single_td(yf_ticker: str, interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data for a single NSE stock via TwelveData.
    Falls back to yfinance on any failure.
    """
    td_symbol = _yf_to_td_nse(yf_ticker)
    if td_symbol is None:
        return _fetch_from_yfinance(yf_ticker, interval)

    api_key    = _get_api_key()
    td_interval = _INTERVAL_MAP.get(interval, interval)

    if api_key:
        df = _fetch_from_twelvedata(yf_ticker, td_symbol, td_interval, api_key)
        if df is not None:
            _save_cache(df, yf_ticker, interval)
            return df
        logger.info("[TD] TwelveData failed for %s — falling back to yfinance", yf_ticker)

    return _fetch_from_yfinance(yf_ticker, interval)


def fetch_stocks_td(tickers=None, interval: str = "1d") -> dict:
    """
    Fetch OHLCV data for NSE stocks via TwelveData (fallback: yfinance).

    Parameters
    ----------
    tickers : list of yfinance ticker strings (e.g. ['RELIANCE.NS', 'TCS.NS'])
              Defaults to ALL_STOCK_TICKERS from config/instruments.py
    interval : '1d' (default)

    Returns
    -------
    dict mapping yfinance ticker → pd.DataFrame
    """
    if tickers is None:
        from config.instruments import ALL_STOCK_TICKERS
        tickers = ALL_STOCK_TICKERS

    results: dict = {}
    api_key = _get_api_key()
    td_interval = _INTERVAL_MAP.get(interval, interval)
    first_td_request = True

    print(f"\n--- Fetching {len(tickers)} NSE stocks via TwelveData ---")

    for yf_ticker in tickers:
        td_symbol = _yf_to_td_nse(yf_ticker)

        # Rate-limit sleep between TwelveData calls
        if api_key and td_symbol and not first_td_request:
            time.sleep(_TD_RATE_LIMIT_SLEEP)

        df = fetch_stock_single_td(yf_ticker, interval=interval)

        if api_key and td_symbol:
            first_td_request = False

        if df is not None:
            results[yf_ticker] = df
        else:
            logger.warning("[TD] Could not fetch %s from any source", yf_ticker)

    print(f"  Done — {len(results)}/{len(tickers)} stocks fetched")
    return results


# ---------------------------------------------------------------------------
# Quick smoke-test when run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pprint

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(levelname)s  %(name)s  %(message)s",
    )

    print("=" * 60)
    print("TwelveData Fetcher — smoke test")
    print("=" * 60)

    key_status = "SET" if _get_api_key() else "NOT SET (will use yfinance fallback)"
    print(f"TWELVEDATA_API_KEY: {key_status}\n")

    # Test single fetch
    print("--- Single fetch: GC=F (Gold) ---")
    gold_df = fetch_comex_single_td("GC=F", interval="1h")
    if gold_df is not None:
        print(f"Shape : {gold_df.shape}")
        print(f"Dtypes:\n{gold_df.dtypes}")
        print(f"Tail  :\n{gold_df.tail(3)}\n")
    else:
        print("FAILED\n")

    # Test full batch
    print("--- Batch fetch: all COMEX tickers ---")
    all_data = fetch_comex_all_td(interval="1h")
    for ticker, df in all_data.items():
        print(f"  {ticker:6s}  {len(df):5d} rows  columns={list(df.columns)}")
