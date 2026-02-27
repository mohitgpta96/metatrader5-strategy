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
    parser.add_argument("--preflight", action="store_true", help="Pre-flight check: verify Telegram bot + data fetch before sending signals")
    parser.add_argument("--subscribers", action="store_true", help="List all subscribers")
    parser.add_argument("--add-user", type=str, help="Add a user by chat ID (e.g., --add-user 123456789)")
    parser.add_argument("--add-channel", type=str, help="Add a channel (e.g., --add-channel @my_channel)")
    parser.add_argument("--track", action="store_true", help="Check active signals against current prices")
    parser.add_argument("--weekly-report", action="store_true", help="Generate 7-day performance report")
    parser.add_argument("--tracker-status", action="store_true", help="Show tracker stats")

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
    elif args.preflight:
        cmd_preflight()
    elif args.subscribers:
        cmd_list_subscribers()
    elif args.add_user:
        cmd_add_user(args.add_user)
    elif args.add_channel:
        cmd_add_channel(args.add_channel)
    elif args.track:
        cmd_track_signals()
    elif args.weekly_report:
        cmd_weekly_report()
    elif args.tracker_status:
        cmd_tracker_status()
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
        print("  8. Manage Subscribers")
        print("  9. Track Active Signals")
        print("  10. Weekly Performance Report (7 days)")
        print("  11. Tracker Status")
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
        elif choice == "8":
            cmd_manage_subscribers()
        elif choice == "9":
            cmd_track_signals()
        elif choice == "10":
            cmd_weekly_report()
        elif choice == "11":
            cmd_tracker_status()
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
    signals, statuses, _ = scan_commodities()
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
        ("GC=F", "Gold", "2y", "1d"),
        ("SI=F", "Silver", "2y", "1d"),
        ("RELIANCE.NS", "Reliance", "2y", "1d"),
        ("TCS.NS", "TCS", "2y", "1d"),
        ("HDFCBANK.NS", "HDFC Bank", "2y", "1d"),
        ("INFY.NS", "Infosys", "2y", "1d"),
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
    """Test Telegram connection (console only - does NOT send to Telegram)."""
    from bot.telegram_bot import get_all_recipients
    from config.settings import TELEGRAM_BOT_TOKEN

    print("\n--- Telegram Bot Config Check ---")
    print(f"Bot Token: {'SET' if TELEGRAM_BOT_TOKEN else 'NOT SET'}")
    recipients = get_all_recipients()
    print(f"Recipients configured: {len(recipients)}")
    for r in recipients:
        print(f"  - {r}")
    print("\n[OK] Config looks good. No test message sent to Telegram.")
    print("     Only real trading signals will be sent to Telegram.")


def cmd_preflight():
    """
    Pre-flight check before sending signals.
    1. Verify Telegram bot is reachable (getMe API call)
    2. Verify market data can be fetched (GC=F quick test)
    Exits with code 1 on any failure — triggers GitHub Actions failure alert.
    """
    import sys
    import requests
    from config.settings import TELEGRAM_BOT_TOKEN

    print("--- Pre-flight Check ---")
    all_ok = True

    # 1. Telegram bot check
    print("[1/2] Checking Telegram bot...")
    if not TELEGRAM_BOT_TOKEN:
        print("  FAIL: TELEGRAM_BOT_TOKEN not set")
        all_ok = False
    else:
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe",
                timeout=10
            )
            data = resp.json()
            if data.get("ok"):
                bot_name = data["result"].get("username", "?")
                print(f"  OK: Bot @{bot_name} is alive")
            else:
                print(f"  FAIL: Telegram API error — {data.get('description', 'unknown')}")
                all_ok = False
        except Exception as e:
            print(f"  FAIL: Cannot reach Telegram — {e}")
            all_ok = False

    # 2. Market data check
    print("[2/2] Checking market data fetch (Gold)...")
    try:
        import yfinance as yf
        import pandas as pd
        df = yf.download("GC=F", period="5d", interval="1h", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df is None or df.empty or len(df) < 5:
            print(f"  FAIL: No data returned for GC=F (got {len(df) if df is not None else 0} rows)")
            all_ok = False
        else:
            print(f"  OK: Got {len(df)} rows for GC=F — last close ${float(df.iloc[-1]['Close']):.2f}")
    except Exception as e:
        print(f"  FAIL: Data fetch error — {e}")
        all_ok = False

    if all_ok:
        print("\n[PREFLIGHT] All checks passed. Proceeding to signal scan.")
    else:
        print("\n[PREFLIGHT] One or more checks FAILED. Aborting signal scan.")
        sys.exit(1)


def cmd_fetch_all():
    """Fetch and cache all market data."""
    from data.fetcher import fetch_all
    fetch_all()


def cmd_check_signals():
    """
    Full scan + send signals via Telegram + log & track signals.
    Used by GitHub Actions cron job.
    """
    from scanner.market_scanner import scan_all
    from bot.telegram_bot import send_signal_alert, check_new_subscribers
    from tracker.signal_logger import log_signal
    from tracker.signal_tracker import track_all_signals

    # Auto-register any new /start users before sending
    new = check_new_subscribers()
    if new > 0:
        print(f"\n{new} new subscriber(s) registered!")

    results = scan_all()

    if not results.get("markets_open", True):
        print("\nAll markets closed. Nothing to send.")
        # Still track existing signals even when markets close
        print("\n--- Tracking Active Signals ---")
        track_all_signals()
        return

    signals = results["signals"]

    if signals:
        # Sort by signal score (best first), send only top 4
        signals_sorted = sorted(signals, key=lambda x: x.get("signal_score", 0), reverse=True)
        top_signals = signals_sorted[:4]

        print(f"\n{len(signals)} signal(s) found. Sending top {len(top_signals)} to Telegram...")
        for signal in top_signals:
            send_signal_alert(signal)
            log_signal(signal)
            print(f"  Sent & Logged: {signal['direction']} {signal['name']} (score={signal.get('signal_score', '?')})")

        if len(signals) > 4:
            skipped = [f"{s['direction']} {s['name']}" for s in signals_sorted[4:]]
            print(f"  Skipped (lower score): {', '.join(skipped)}")
    else:
        print("\nNo signals at this time.")

    # Track all active signals against current prices
    print("\n--- Tracking Active Signals ---")
    track_all_signals()


def cmd_list_subscribers():
    """List all subscribers."""
    from bot.telegram_bot import list_subscribers, check_new_subscribers
    check_new_subscribers()
    list_subscribers()


def cmd_add_user(chat_id):
    """Manually add a user by chat ID."""
    from bot.telegram_bot import add_subscriber
    added = add_subscriber(chat_id, name="Manual")
    if added:
        print(f"User {chat_id} added successfully!")
    else:
        print(f"User {chat_id} already exists.")


def cmd_add_channel(channel):
    """Add a Telegram channel."""
    if not channel.startswith("@"):
        channel = f"@{channel}"
    from bot.telegram_bot import add_subscriber
    added = add_subscriber(channel, name=f"Channel {channel}")
    if added:
        print(f"Channel {channel} added!")
        print(f"IMPORTANT: Make the bot an admin of {channel} first!")
    else:
        print(f"Channel {channel} already exists.")


def cmd_manage_subscribers():
    """Interactive subscriber management."""
    from bot.telegram_bot import (
        list_subscribers, check_new_subscribers, add_subscriber,
        remove_subscriber, get_all_recipients, send_message_sync
    )

    while True:
        print("\n" + "-" * 40)
        print("  SUBSCRIBER MANAGEMENT")
        print("-" * 40)
        print("  1. List all subscribers")
        print("  2. Check for new /start users")
        print("  3. Add user manually (chat ID)")
        print("  4. Add Telegram channel")
        print("  5. Remove subscriber")
        print("  6. Send test to all")
        print("  0. Back to main menu")
        print("-" * 40)

        choice = input("\nSelect: ").strip()

        if choice == "1":
            list_subscribers()

        elif choice == "2":
            new = check_new_subscribers()
            print(f"{new} new subscriber(s) found.")
            list_subscribers()

        elif choice == "3":
            chat_id = input("Enter chat ID: ").strip()
            name = input("Enter name (optional): ").strip()
            added = add_subscriber(chat_id, name)
            print(f"{'Added!' if added else 'Already exists.'}")

        elif choice == "4":
            channel = input("Enter channel username (@...): ").strip()
            if not channel.startswith("@"):
                channel = f"@{channel}"
            added = add_subscriber(channel, f"Channel {channel}")
            if added:
                print(f"Channel {channel} added!")
                print("Make sure the bot is an ADMIN of this channel!")
            else:
                print("Already exists.")

        elif choice == "5":
            chat_id = input("Enter chat ID or @channel to remove: ").strip()
            removed = remove_subscriber(chat_id)
            print(f"{'Removed!' if removed else 'Not found.'}")

        elif choice == "6":
            recipients = get_all_recipients()
            print(f"\n[INFO] {len(recipients)} recipient(s) configured.")
            print("       Test messages are NOT sent to Telegram.")
            print("       Only real trading signals will be sent.")

        elif choice == "0":
            break


def cmd_track_signals():
    """Manually trigger signal tracking."""
    from tracker.signal_tracker import track_all_signals
    from tracker.signal_logger import get_log_stats
    print("Running signal tracker...")
    track_all_signals()
    stats = get_log_stats()
    print(f"\nTracker Stats: {stats['active']} active, {stats['resolved_pending']} resolved, {stats['archived']} archived")


def cmd_weekly_report():
    """Generate 7-day report (internal only, NOT sent to Telegram)."""
    from tracker.weekly_report import generate_weekly_report
    from tracker.signal_logger import archive_resolved

    print("Generating 7-day performance report...\n")
    report, data = generate_weekly_report()
    print(report)

    # Archive resolved signals
    if data.get("total", 0) > 0:
        archived = archive_resolved()
        if archived > 0:
            print(f"\nArchived {archived} resolved signal(s).")


def cmd_tracker_status():
    """Show tracker stats."""
    from tracker.signal_logger import get_log_stats, get_active_signals
    stats = get_log_stats()
    print("\nSignal Tracker Status")
    print("-" * 35)
    print(f"  Active:    {stats['active']}")
    print(f"  Resolved:  {stats['resolved_pending']}")
    print(f"  Archived:  {stats['archived']}")
    print(f"  Total:     {stats['total']}")

    active = get_active_signals()
    if active:
        print(f"\nActive Signals:")
        for s in active:
            entry = s["entry"]
            curr = s.get("current_price", entry)
            d = s["direction"]
            pnl = (curr - entry) if d == "BUY" else (entry - curr)
            print(f"  {s['signal_id']} | {d:4} {s['name'][:20]:<20} | Entry: {entry:.2f} | Now: {curr:.2f} | P&L: {pnl:+.2f}")


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
