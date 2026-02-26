#!/usr/bin/env python3
"""
MetaTrader5 Strategy - Multi-Market Trading Signal System
Main CLI entry point.

Usage:
    python run.py                  # Interactive menu
    python run.py --scan-all       # Full market scan
    python run.py --scan-gold      # Gold/Silver/Crude only
    python run.py --scan-stocks    # NIFTY 100 stocks only
    python run.py --digest         # Daily digest
    python run.py --backtest       # Run backtests
    python run.py --test-telegram  # Test Telegram bot
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    parser = argparse.ArgumentParser(description="Multi-Market Trading Signal System")
    parser.add_argument("--scan-all", action="store_true", help="Full market scan (all instruments)")
    parser.add_argument("--scan-gold", action="store_true", help="Scan Gold, Silver, Crude Oil only")
    parser.add_argument("--scan-stocks", action="store_true", help="Scan NIFTY 100 stocks only")
    parser.add_argument("--digest", action="store_true", help="Generate and send daily digest")
    parser.add_argument("--backtest", action="store_true", help="Run backtests on Gold + top stocks")
    parser.add_argument("--test-telegram", action="store_true", help="Send test message to Telegram")
    parser.add_argument("--check-signals", action="store_true", help="Scan all + send signals via Telegram (for GitHub Actions)")

    args = parser.parse_args()

    if args.scan_all:
        cmd_scan_all()
    elif args.scan_gold:
        cmd_scan_commodities()
    elif args.scan_stocks:
        cmd_scan_stocks()
    elif args.digest:
        cmd_daily_digest()
    elif args.backtest:
        cmd_backtest()
    elif args.test_telegram:
        cmd_test_telegram()
    elif args.check_signals:
        cmd_check_signals()
    else:
        interactive_menu()


def interactive_menu():
    """Interactive menu for local use."""
    while True:
        print("\n" + "=" * 50)
        print("  METATRADER5 STRATEGY - SIGNAL SYSTEM")
        print("=" * 50)
        print("  1. Full Market Scan (Gold + Stocks + Indices)")
        print("  2. Scan Commodities Only (Gold, Silver, Crude)")
        print("  3. Scan NIFTY 100 Stocks Only")
        print("  4. Generate Daily Digest")
        print("  5. Run Backtest")
        print("  6. Test Telegram Bot")
        print("  7. Fetch & Cache All Data")
        print("  0. Exit")
        print("=" * 50)

        choice = input("\nSelect option: ").strip()

        if choice == "1":
            cmd_scan_all()
        elif choice == "2":
            cmd_scan_commodities()
        elif choice == "3":
            cmd_scan_stocks()
        elif choice == "4":
            cmd_daily_digest()
        elif choice == "5":
            cmd_backtest()
        elif choice == "6":
            cmd_test_telegram()
        elif choice == "7":
            cmd_fetch_all()
        elif choice == "0":
            print("Bye!")
            break
        else:
            print("Invalid option. Try again.")


def cmd_scan_all():
    """Full market scan."""
    from scanner.market_scanner import scan_all
    results = scan_all()
    _print_signals(results["signals"])


def cmd_scan_commodities():
    """Commodities only scan."""
    from scanner.market_scanner import scan_commodities
    signals, statuses = scan_commodities()
    _print_signals(signals)


def cmd_scan_stocks():
    """NIFTY 100 scan."""
    from scanner.market_scanner import scan_stocks
    signals, statuses = scan_stocks()
    _print_signals(signals)


def cmd_daily_digest():
    """Generate and optionally send daily digest."""
    from scanner.daily_digest import generate_digest
    from bot.telegram_bot import send_daily_digest

    print("Generating daily digest...")
    digest = generate_digest()
    print("\n" + digest)

    send = input("\nSend to Telegram? (y/n): ").strip().lower()
    if send == "y":
        send_daily_digest(digest)


def cmd_backtest():
    """Run backtests."""
    import pandas as pd
    import yfinance as yf
    from backtest.engine import backtest_strategy, print_results

    instruments = [
        ("GC=F", "Gold", "1y", "1d"),
        ("SI=F", "Silver", "1y", "1d"),
        ("RELIANCE.NS", "Reliance", "1y", "1d"),
        ("TCS.NS", "TCS", "1y", "1d"),
        ("HDFCBANK.NS", "HDFC Bank", "1y", "1d"),
        ("INFY.NS", "Infosys", "1y", "1d"),
    ]

    all_results = []
    for ticker, name, period, interval in instruments:
        print(f"\nBacktesting {name} ({ticker})...")
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.title() for c in df.columns]

        if df.empty:
            print(f"  No data for {name}")
            continue

        results = backtest_strategy(df, ticker=ticker)
        print_results(results)
        if results and results["total_trades"] > 0:
            all_results.append(results)

    if all_results:
        print(f"\n\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")
        print(f"{'Instrument':<20} {'Trades':<8} {'Win%':<8} {'PF':<8} {'Return':<10} {'MaxDD':<8}")
        print("-" * 60)
        for r in all_results:
            print(f"{r['name']:<20} {r['total_trades']:<8} {r['win_rate']}%{'':<4} "
                  f"{r['profit_factor']:<8} {r['net_return_pct']}%{'':<5} {r['max_drawdown_pct']}%")


def cmd_test_telegram():
    """Test Telegram connection."""
    from bot.telegram_bot import send_message_sync

    print("Sending test message to Telegram...")
    success = send_message_sync(
        "TEST MESSAGE\n"
        "==================\n"
        "MetaTrader5 Strategy Bot is working!\n"
        "==================\n"
        "Multi-Market Signal System ready."
    )
    if success:
        print("Message sent! Check your Telegram.")
    else:
        print("Message printed to console (Telegram not configured yet).")


def cmd_fetch_all():
    """Fetch and cache all market data."""
    from data.fetcher import fetch_all
    fetch_all()


def cmd_check_signals():
    """
    Full scan + send signals via Telegram.
    Used by GitHub Actions cron job.
    """
    from scanner.market_scanner import scan_all
    from bot.telegram_bot import send_signal_alert, send_daily_digest
    from bot.formatter import format_signal

    results = scan_all()
    signals = results["signals"]

    if signals:
        print(f"\n{len(signals)} signal(s) found! Sending to Telegram...")
        for signal in signals:
            send_signal_alert(signal)
            print(f"  Sent: {signal['direction']} {signal['name']}")
    else:
        print("\nNo signals at this time.")


def _print_signals(signals):
    """Print formatted signals."""
    if not signals:
        print("\nNo active signals right now.")
        return

    from bot.formatter import format_signal
    print(f"\n{'=' * 40}")
    print(f"  {len(signals)} ACTIVE SIGNAL(S)")
    print(f"{'=' * 40}")
    for signal in signals:
        print(f"\n{format_signal(signal)}")


if __name__ == "__main__":
    main()
