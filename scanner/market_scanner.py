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
from strategy.macro_analysis import generate_market_intelligence, format_intelligence_report
from config.instruments import (
    ALL_COMMODITY_TICKERS, ALL_INDEX_TICKERS, ALL_STOCK_TICKERS,
    ALL_MCX_TICKERS, MCX_COMMODITIES, COMMODITIES, get_display_name,
)
from config.market_hours import is_nse_open, is_mcx_open, is_commodity_open, market_status_summary


def scan_commodities():
    """
    Scan Gold, Silver, Crude Oil etc. for signals.
    Returns signals, statuses, and cached data dict for MCX reuse.
    """
    print("\n--- Scanning Global Commodity Futures ---")
    signals = []
    statuses = []
    cached_data = {}  # ticker -> (df_1h, df_4h) for MCX reuse

    for ticker in ALL_COMMODITY_TICKERS:
        name = get_display_name(ticker)
        print(f"  Checking {name}...")

        # Fetch 1H data (primary) and 4H data (confirmation)
        df_1h = fetch_single(ticker, period="60d", interval="1h")
        df_4h = fetch_single(ticker, period="60d", interval="4h")

        # Cache for MCX reuse
        cached_data[ticker] = (df_1h, df_4h)

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

    return signals, statuses, cached_data


def scan_mcx(already_scanned=None):
    """
    Scan MCX Indian Commodity Futures for signals.
    Uses international futures tickers as proxy (MCX follows these exactly).
    If a ticker was already scanned in global commodities, reuses that data.
    """
    print("\n--- Scanning MCX Indian Commodity Futures ---")
    signals = []
    statuses = []
    already_scanned = already_scanned or {}

    for key, info in MCX_COMMODITIES.items():
        ticker = info["yf_ticker"]
        name = info["name"]
        print(f"  Checking {name} ({ticker})...")

        # Reuse data if already fetched in global commodity scan
        if ticker in already_scanned:
            df_1h, df_4h = already_scanned[ticker]
        else:
            df_1h = fetch_single(ticker, period="60d", interval="1h")
            df_4h = fetch_single(ticker, period="60d", interval="4h")

        if df_1h is None or df_1h.empty:
            print(f"    [SKIP] No data for {name}")
            continue

        signal = check_signal(df_1h, df_confirmation=df_4h, ticker=ticker)
        if signal:
            # Override type and name for MCX
            signal["type"] = "mcx_commodity"
            signal["name"] = name
            signal["mcx_key"] = key
            signals.append(signal)
            print(f"    SIGNAL: {signal['direction']} at ${signal['entry']}")
        else:
            print(f"    No signal")

        status = check_trend_status(df_1h, ticker=ticker)
        if status:
            status["name"] = name
            status["type"] = "mcx_commodity"
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
    print(f"\n--- Scanning {len(tickers)} Stock Futures ---")
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
    Full market scan: Commodities + Indices + Stocks + Market Intelligence.
    Only scans markets that are currently OPEN/LIVE.
    Returns all signals, statuses, and intelligence report.
    """
    commodity_live = is_commodity_open()
    mcx_live = is_mcx_open()
    nse_live = is_nse_open()

    print("=" * 60)
    print("MULTI-MARKET FUTURES SCAN")
    print("=" * 60)
    print(f"\n{market_status_summary()}")

    if not commodity_live and not mcx_live and not nse_live:
        print("\n[!] ALL MARKETS CLOSED. No signals to generate.")
        return {
            "signals": [], "statuses": [],
            "commodity_signals": [], "commodity_statuses": [],
            "mcx_signals": [], "mcx_statuses": [],
            "index_statuses": [],
            "stock_signals": [], "stock_statuses": [],
            "intelligence": None, "intelligence_report": None,
            "markets_open": False,
        }

    # Market Intelligence (macro + geo-political + news)
    print("\n--- Generating Market Intelligence ---")
    try:
        intel = generate_market_intelligence()
        intel_report = format_intelligence_report(intel)
        print("  Intelligence report generated.")
    except Exception as e:
        print(f"  [WARN] Intelligence report failed: {e}")
        intel = None
        intel_report = None

    commodity_signals = []
    commodity_statuses = []
    commodity_cached = {}
    mcx_signals = []
    mcx_statuses = []
    index_statuses = []
    stock_signals = []
    stock_statuses = []

    # Global Commodities - only if COMEX/NYMEX is live
    if commodity_live:
        commodity_signals, commodity_statuses, commodity_cached = scan_commodities()
        if intel:
            commodity_signals = _filter_signals_by_outlook(commodity_signals, intel)
    else:
        print("\n--- COMEX/NYMEX CLOSED - Skipping Global Commodities ---")

    # MCX Indian Commodities - only if MCX is live
    if mcx_live:
        mcx_signals, mcx_statuses = scan_mcx(already_scanned=commodity_cached)
        if intel:
            mcx_signals = _filter_signals_by_outlook(mcx_signals, intel)
    else:
        print("\n--- MCX CLOSED - Skipping Indian Commodities ---")

    # Indices & Stocks - only if NSE is live
    if nse_live:
        index_statuses = scan_indices()
        stock_signals, stock_statuses = scan_stocks()
        if intel:
            stock_signals = _filter_signals_by_outlook(stock_signals, intel)
    else:
        print("\n--- NSE CLOSED - Skipping Stocks & Indices ---")

    all_signals = commodity_signals + mcx_signals + stock_signals
    all_statuses = commodity_statuses + mcx_statuses + index_statuses + stock_statuses

    print(f"\n{'=' * 60}")
    print(f"SCAN COMPLETE")
    print(f"  Total Signals: {len(all_signals)}")
    if commodity_live:
        print(f"  - Global Commodity Futures: {len(commodity_signals)}")
    if mcx_live:
        print(f"  - MCX Indian Commodities: {len(mcx_signals)}")
    if nse_live:
        print(f"  - Stock Futures: {len(stock_signals)}")
    if intel:
        print(f"  Risk Level: {intel['risk_level']} ({intel['risk_score']}/100)")
        print(f"  Gold: {intel['gold_outlook']} | Oil: {intel['oil_outlook']} | Stocks: {intel['stock_outlook']}")
    print(f"{'=' * 60}")

    return {
        "signals": all_signals,
        "statuses": all_statuses,
        "commodity_signals": commodity_signals,
        "commodity_statuses": commodity_statuses,
        "mcx_signals": mcx_signals,
        "mcx_statuses": mcx_statuses,
        "index_statuses": index_statuses,
        "stock_signals": stock_signals,
        "stock_statuses": stock_statuses,
        "intelligence": intel,
        "intelligence_report": intel_report,
        "markets_open": True,
    }


def _filter_signals_by_outlook(signals, intel):
    """
    Add macro context to signals. Flag signals that go AGAINST macro outlook.
    Does NOT remove signals - just adds a warning label.
    """
    filtered = []
    for signal in signals:
        ticker = signal.get("ticker", "")
        direction = signal.get("direction", "")
        sig_type = signal.get("type", "")

        # Determine relevant outlook
        outlook = "NEUTRAL"
        if sig_type == "commodity":
            if "GC=F" in ticker or "XAUUSD" in ticker:
                outlook = intel.get("gold_outlook", "NEUTRAL")
            elif "SI=F" in ticker:
                outlook = intel.get("gold_outlook", "NEUTRAL")  # Silver follows gold
            elif "CL=F" in ticker or "BZ=F" in ticker:
                outlook = intel.get("oil_outlook", "NEUTRAL")
            elif "NG=F" in ticker:
                outlook = intel.get("oil_outlook", "NEUTRAL")
            elif "HG=F" in ticker or "PL=F" in ticker:
                outlook = intel.get("stock_outlook", "NEUTRAL")  # Industrial metals follow stocks
        else:
            outlook = intel.get("stock_outlook", "NEUTRAL")

        # Add macro context to signal
        signal["macro_outlook"] = outlook
        signal["macro_risk"] = intel.get("risk_level", "MEDIUM")

        # Flag if signal direction conflicts with macro outlook
        if direction == "BUY" and outlook == "BEARISH":
            signal["macro_warning"] = "CAUTION: Macro outlook is BEARISH"
        elif direction == "SELL" and outlook == "BULLISH":
            signal["macro_warning"] = "CAUTION: Macro outlook is BULLISH"
        else:
            signal["macro_warning"] = None

        filtered.append(signal)

    return filtered


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
