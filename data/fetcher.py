"""
Market data fetcher using yfinance.
Downloads OHLCV data for all instruments and caches to CSV.
"""
import sys
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    DATA_CACHE_DIR,
    HISTORY_PERIOD_INTRADAY,
    HISTORY_PERIOD_DAILY,
    BACKTEST_PERIOD,
    PRIMARY_TIMEFRAME,
    STOCK_TIMEFRAME,
)
from config.instruments import (
    ALL_COMMODITY_TICKERS,
    ALL_INDEX_TICKERS,
    ALL_STOCK_TICKERS,
    get_instrument_type,
)


def fetch_single(ticker, period=None, interval=None):
    """Fetch OHLCV data for a single ticker."""
    inst_type = get_instrument_type(ticker)

    if interval is None:
        interval = PRIMARY_TIMEFRAME if inst_type == "commodity" else STOCK_TIMEFRAME

    if period is None:
        period = HISTORY_PERIOD_INTRADAY if interval in ("1m", "5m", "15m", "30m", "1h") else HISTORY_PERIOD_DAILY

    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            print(f"  [WARN] No data for {ticker}")
            return None

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Ensure standard column names
        df.columns = [c.title() for c in df.columns]

        # Cache to CSV
        safe_name = ticker.replace("=", "_").replace("^", "IDX_").replace(".", "_")
        cache_path = DATA_CACHE_DIR / f"{safe_name}_{interval}.csv"
        df.to_csv(cache_path)

        return df
    except Exception as e:
        print(f"  [ERROR] Failed to fetch {ticker}: {e}")
        return None


def fetch_batch(tickers, period=None, interval="1d"):
    """Fetch data for multiple tickers in one batch call (faster)."""
    if period is None:
        period = HISTORY_PERIOD_INTRADAY if interval in ("1m", "5m", "15m", "30m", "1h") else HISTORY_PERIOD_DAILY

    try:
        data = yf.download(
            tickers=tickers,
            period=period,
            interval=interval,
            threads=True,
            group_by="ticker",
            progress=False,
            auto_adjust=True,
        )
        return data
    except Exception as e:
        print(f"  [ERROR] Batch fetch failed: {e}")
        return None


def fetch_commodities(interval=None):
    """Fetch all commodity data (Gold, Silver, Crude)."""
    interval = interval or PRIMARY_TIMEFRAME
    results = {}
    for ticker in ALL_COMMODITY_TICKERS:
        print(f"  Fetching {ticker}...")
        df = fetch_single(ticker, interval=interval)
        if df is not None:
            results[ticker] = df
    return results


def fetch_indices(interval=None):
    """Fetch Indian index data (NIFTY, BANK NIFTY)."""
    interval = interval or STOCK_TIMEFRAME
    results = {}
    for ticker in ALL_INDEX_TICKERS:
        print(f"  Fetching {ticker}...")
        df = fetch_single(ticker, interval=interval)
        if df is not None:
            results[ticker] = df
    return results


def fetch_stocks(tickers=None, interval=None):
    """Fetch NIFTY 100 stock data. Returns dict of {ticker: DataFrame}."""
    tickers = tickers or ALL_STOCK_TICKERS
    interval = interval or STOCK_TIMEFRAME
    results = {}

    # Batch download for speed
    print(f"  Fetching {len(tickers)} stocks in batch...")
    batch_data = fetch_batch(tickers, interval=interval)

    if batch_data is None or batch_data.empty:
        print("  [WARN] Batch download returned empty. Trying one by one...")
        for ticker in tickers:
            df = fetch_single(ticker, interval=interval)
            if df is not None:
                results[ticker] = df
            time.sleep(0.5)
        return results

    # Extract individual DataFrames from batch
    for ticker in tickers:
        try:
            if isinstance(batch_data.columns, pd.MultiIndex):
                df = batch_data[ticker].copy()
            else:
                df = batch_data.copy()

            df = df.dropna(how="all")
            if not df.empty:
                df.columns = [c.title() for c in df.columns]
                results[ticker] = df

                # Cache
                safe_name = ticker.replace(".", "_")
                cache_path = DATA_CACHE_DIR / f"{safe_name}_{interval}.csv"
                df.to_csv(cache_path)
        except (KeyError, Exception):
            continue

    print(f"  Got data for {len(results)}/{len(tickers)} stocks")
    return results


def fetch_all():
    """Fetch everything: commodities + indices + stocks."""
    print("=" * 50)
    print("FETCHING ALL MARKET DATA")
    print("=" * 50)

    print("\n--- Commodities (Gold, Silver, Crude) ---")
    commodities = fetch_commodities()

    print("\n--- Indian Indices (NIFTY, BANK NIFTY) ---")
    indices = fetch_indices()

    print("\n--- NIFTY 100 Stocks ---")
    stocks = fetch_stocks()

    total = len(commodities) + len(indices) + len(stocks)
    print(f"\n{'=' * 50}")
    print(f"TOTAL: {total} instruments fetched successfully")
    print(f"{'=' * 50}")

    return {
        "commodities": commodities,
        "indices": indices,
        "stocks": stocks,
    }


def load_cached(ticker, interval="1d"):
    """Load data from cache if available."""
    safe_name = ticker.replace("=", "_").replace("^", "IDX_").replace(".", "_")
    cache_path = DATA_CACHE_DIR / f"{safe_name}_{interval}.csv"
    if cache_path.exists():
        df = pd.read_csv(cache_path, index_col=0, parse_dates=True)
        return df
    return None


if __name__ == "__main__":
    # Quick test - fetch Gold and 1 stock
    print("Testing data fetcher...")
    gold = fetch_single("GC=F", period="5d", interval="1h")
    if gold is not None:
        print(f"\nGold data: {len(gold)} candles")
        print(gold.tail(3))

    print("\n---")
    reliance = fetch_single("RELIANCE.NS", period="1mo", interval="1d")
    if reliance is not None:
        print(f"\nReliance data: {len(reliance)} candles")
        print(reliance.tail(3))
