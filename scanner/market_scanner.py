"""
Multi-market scanner.
Scans Gold, Silver, Crude Oil, NIFTY 100 stocks, and Indices.
Finds BUY/SELL signals and generates alerts.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.fetcher import fetch_single, fetch_stocks
from strategy.signals import check_signal, check_trend_status
from config.instruments import (
    ALL_COMMODITY_TICKERS, ALL_INDEX_TICKERS, ALL_STOCK_TICKERS,
    COMMODITIES, get_display_name,
)


def scan_commodities():
    """Scan Gold, Silver, Crude Oil for signals."""
    print("\n--- Scanning Commodities ---")
    signals = []
    statuses = []

    for ticker in ALL_COMMODITY_TICKERS:
        name = get_display_name(ticker)
        print(f"  Checking {name}...")

        # Fetch 1H data (primary) and 4H data (confirmation)
        df_1h = fetch_single(ticker, period="60d", interval="1h")
        df_4h = fetch_single(ticker, period="60d", interval="4h")

        if df_1h is None:
            print(f"    [SKIP] No data for {name}")
            continue

        # Check for signal
        signal = check_signal(df_1h, df_confirmation=df_4h, ticker=ticker)
        if signal:
            signals.append(signal)
            print(f"    SIGNAL: {signal['direction']} at ${signal['entry']}")
        else:
            print(f"    No signal")

        # Always get status for daily digest
        status = check_trend_status(df_1h, ticker=ticker)
        if status:
            statuses.append(status)

    return signals, statuses


def scan_indices():
    """Scan NIFTY and BANK NIFTY for trend status."""
    print("\n--- Scanning Indices ---")
    statuses = []

    for ticker in ALL_INDEX_TICKERS:
        name = get_display_name(ticker)
        print(f"  Checking {name}...")

        df = fetch_single(ticker, period="1y", interval="1d")
        if df is None:
            continue

        status = check_trend_status(df, ticker=ticker)
        if status:
            statuses.append(status)
            print(f"    {name}: {status['condition']} (RSI: {status['rsi']})")

    return statuses


def scan_stocks(tickers=None):
    """Scan NIFTY 100 stocks for signals."""
    tickers = tickers or ALL_STOCK_TICKERS
    print(f"\n--- Scanning {len(tickers)} Stocks ---")
    signals = []
    statuses = []

    # Fetch all stock data at once (batch)
    stock_data = fetch_stocks(tickers, interval="1d")

    for ticker in tickers:
        df = stock_data.get(ticker)
        if df is None or df.empty:
            continue

        name = get_display_name(ticker)

        # For stocks, use daily data only (no separate confirmation timeframe)
        signal = check_signal(df, ticker=ticker)
        if signal:
            signals.append(signal)
            print(f"  SIGNAL: {signal['direction']} {name} at Rs {signal['entry']}")

        status = check_trend_status(df, ticker=ticker)
        if status:
            statuses.append(status)

    buy_count = sum(1 for s in signals if s["direction"] == "BUY")
    sell_count = sum(1 for s in signals if s["direction"] == "SELL")
    print(f"\n  Results: {buy_count} BUY + {sell_count} SELL signals out of {len(tickers)} stocks")

    return signals, statuses


def scan_all():
    """
    Full market scan: Commodities + Indices + Stocks.
    Returns all signals and statuses.
    """
    print("=" * 60)
    print("MULTI-MARKET SCAN")
    print("=" * 60)

    # Commodities
    commodity_signals, commodity_statuses = scan_commodities()

    # Indices
    index_statuses = scan_indices()

    # Stocks
    stock_signals, stock_statuses = scan_stocks()

    all_signals = commodity_signals + stock_signals
    all_statuses = commodity_statuses + index_statuses + stock_statuses

    print(f"\n{'=' * 60}")
    print(f"SCAN COMPLETE")
    print(f"  Total Signals: {len(all_signals)}")
    print(f"  - Commodity: {len(commodity_signals)}")
    print(f"  - Stocks: {len(stock_signals)}")
    print(f"{'=' * 60}")

    return {
        "signals": all_signals,
        "statuses": all_statuses,
        "commodity_signals": commodity_signals,
        "commodity_statuses": commodity_statuses,
        "index_statuses": index_statuses,
        "stock_signals": stock_signals,
        "stock_statuses": stock_statuses,
    }


if __name__ == "__main__":
    results = scan_all()

    if results["signals"]:
        print("\n\nACTIVE SIGNALS:")
        print("-" * 40)
        for s in results["signals"]:
            currency = "$" if s["type"] == "commodity" else "Rs "
            print(f"  {s['direction']} {s['name']} @ {currency}{s['entry']} "
                  f"| SL: {currency}{s['stop_loss']} | TP1: {currency}{s['tp1']} "
                  f"| Lot: {s['lot_size']}")
