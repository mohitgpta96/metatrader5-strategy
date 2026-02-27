"""
Signal Tracker - Checks active signals against current prices.
Determines if SL, TP1, or TP2 were hit.
Runs every hour via GitHub Actions alongside signal_check.
"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tracker.signal_logger import (
    get_active_signals, update_signal, get_log_stats,
)

# Signals expire after 7 days if no SL/TP hit
SIGNAL_EXPIRY_DAYS = 7


def track_all_signals():
    """
    Check all active signals against current market prices.
    Updates status: TP1_HIT, TP2_HIT, SL_HIT, or EXPIRED.
    Returns summary of what happened.
    """
    active = get_active_signals()
    if not active:
        print("[TRACKER] No active signals to track.")
        return {"checked": 0, "tp1_hits": 0, "tp2_hits": 0, "sl_hits": 0, "expired": 0}

    print(f"[TRACKER] Checking {len(active)} active signal(s)...")

    # Group by ticker to minimize API calls
    ticker_groups = {}
    for sig in active:
        ticker = sig["ticker"]
        if ticker not in ticker_groups:
            ticker_groups[ticker] = []
        ticker_groups[ticker].append(sig)

    # Fetch current + recent price data for each ticker
    price_data = {}
    for ticker in ticker_groups:
        try:
            df = yf.download(ticker, period="7d", interval="1h", progress=False, auto_adjust=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [c.title() for c in df.columns]
            if not df.empty:
                price_data[ticker] = df
        except Exception as e:
            print(f"  [WARN] Failed to fetch {ticker}: {e}")

    tp1_hits = 0
    tp2_hits = 0
    sl_hits = 0
    expired = 0
    now = datetime.now(timezone.utc)

    for sig in active:
        ticker = sig["ticker"]
        df = price_data.get(ticker)

        if df is None or df.empty:
            continue

        # Get price data since signal was generated
        sig_time = datetime.fromisoformat(sig["timestamp"])
        if sig_time.tzinfo is None:
            sig_time = sig_time.replace(tzinfo=timezone.utc)

        # Filter bars since signal entry
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        recent = df[df.index >= sig_time]

        if recent.empty:
            # Signal is newer than latest candle — use only the current candle
            recent = df.iloc[[-1]]

        current_price = float(df.iloc[-1]["Close"])
        high_since = float(recent["High"].max())
        low_since = float(recent["Low"].min())

        entry = sig["entry"]
        sl = sig["stop_loss"]
        tp1 = sig["tp1"]
        tp2 = sig["tp2"]
        direction = sig["direction"]

        updates = {
            "current_price": round(current_price, 2),
            "last_checked": now.isoformat(),
            "checks_count": sig["checks_count"] + 1,
        }

        if direction == "BUY":
            updates["highest_price"] = round(max(sig.get("highest_price", entry), high_since), 2)
            updates["lowest_price"] = round(min(sig.get("lowest_price", entry), low_since), 2)
            updates["max_favorable"] = round(high_since - entry, 2)
            updates["max_adverse"] = round(entry - low_since, 2)

            # Check SL hit (Low went below SL)
            if low_since <= sl:
                updates["status"] = "SL_HIT"
                updates["sl_hit"] = True
                updates["sl_hit_time"] = now.isoformat()
                updates["pnl_at_close"] = round(sl - entry, 2)
                sl_hits += 1
                print(f"  [SL HIT] {sig['name']} BUY @ {entry} -> SL {sl}")

            # Check TP2 (High went above TP2) - check TP2 first (better outcome)
            elif high_since >= tp2:
                updates["status"] = "TP2_HIT"
                updates["tp1_hit"] = True
                updates["tp2_hit"] = True
                updates["tp2_hit_time"] = now.isoformat()
                updates["pnl_at_close"] = round(tp2 - entry, 2)
                tp2_hits += 1
                print(f"  [TP2 HIT] {sig['name']} BUY @ {entry} -> TP2 {tp2}")

            # Check TP1 (High went above TP1)
            elif high_since >= tp1:
                if not sig.get("tp1_hit"):
                    updates["tp1_hit"] = True
                    updates["tp1_hit_time"] = now.isoformat()
                # Check if also hit SL after TP1 (trailing scenario)
                # For simplicity: mark as TP1_HIT (partial profit)
                updates["status"] = "TP1_HIT"
                updates["pnl_at_close"] = round(tp1 - entry, 2)
                tp1_hits += 1
                print(f"  [TP1 HIT] {sig['name']} BUY @ {entry} -> TP1 {tp1}")

        elif direction == "SELL":
            updates["highest_price"] = round(max(sig.get("highest_price", entry), high_since), 2)
            updates["lowest_price"] = round(min(sig.get("lowest_price", entry), low_since), 2)
            updates["max_favorable"] = round(entry - low_since, 2)
            updates["max_adverse"] = round(high_since - entry, 2)

            # Check SL hit (High went above SL)
            if high_since >= sl:
                updates["status"] = "SL_HIT"
                updates["sl_hit"] = True
                updates["sl_hit_time"] = now.isoformat()
                updates["pnl_at_close"] = round(entry - sl, 2)
                sl_hits += 1
                print(f"  [SL HIT] {sig['name']} SELL @ {entry} -> SL {sl}")

            # Check TP2 first
            elif low_since <= tp2:
                updates["status"] = "TP2_HIT"
                updates["tp1_hit"] = True
                updates["tp2_hit"] = True
                updates["tp2_hit_time"] = now.isoformat()
                updates["pnl_at_close"] = round(entry - tp2, 2)
                tp2_hits += 1
                print(f"  [TP2 HIT] {sig['name']} SELL @ {entry} -> TP2 {tp2}")

            # Check TP1
            elif low_since <= tp1:
                if not sig.get("tp1_hit"):
                    updates["tp1_hit"] = True
                    updates["tp1_hit_time"] = now.isoformat()
                updates["status"] = "TP1_HIT"
                updates["pnl_at_close"] = round(entry - tp1, 2)
                tp1_hits += 1
                print(f"  [TP1 HIT] {sig['name']} SELL @ {entry} -> TP1 {tp1}")

        # Check expiry (signal older than 7 days with no resolution)
        age = (now - sig_time).total_seconds() / 86400
        if updates.get("status", sig["status"]) == "ACTIVE" and age > SIGNAL_EXPIRY_DAYS:
            updates["status"] = "EXPIRED"
            # PnL at expiry = current price vs entry
            if direction == "BUY":
                updates["pnl_at_close"] = round(current_price - entry, 2)
            else:
                updates["pnl_at_close"] = round(entry - current_price, 2)
            expired += 1
            print(f"  [EXPIRED] {sig['name']} {direction} @ {entry} (7 days, no SL/TP hit)")

        update_signal(sig["signal_id"], updates)

    summary = {
        "checked": len(active),
        "tp1_hits": tp1_hits,
        "tp2_hits": tp2_hits,
        "sl_hits": sl_hits,
        "expired": expired,
        "still_active": len(active) - tp1_hits - tp2_hits - sl_hits - expired,
    }

    print(f"[TRACKER] Results: {tp1_hits} TP1 | {tp2_hits} TP2 | {sl_hits} SL | {expired} Expired | {summary['still_active']} Still Active")
    return summary


if __name__ == "__main__":
    print("Running signal tracker...")
    result = track_all_signals()
    print(f"\nStats: {get_log_stats()}")
