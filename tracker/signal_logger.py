"""
Signal Logger - Saves every generated signal to a JSON log.
Each signal gets a unique ID and timestamp for tracking.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "signals_log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

ACTIVE_FILE = LOG_DIR / "active_signals.json"
HISTORY_FILE = LOG_DIR / "signal_history.json"


def _load_json(filepath):
    if filepath.exists():
        try:
            with open(filepath) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_json(filepath, data):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)


def log_signal(signal):
    """
    Log a new signal to active_signals.json.
    Adds: signal_id, timestamp, status, outcome fields.
    Returns the signal_id.
    """
    active = _load_json(ACTIVE_FILE)

    # Check for duplicate (same ticker + direction within last 4 hours)
    now = datetime.now(timezone.utc)
    for existing in active:
        if (existing["ticker"] == signal["ticker"]
                and existing["direction"] == signal["direction"]
                and existing["status"] == "ACTIVE"):
            # Already tracking this signal
            return existing["signal_id"]

    signal_id = str(uuid.uuid4())[:8]

    tracked = {
        "signal_id": signal_id,
        "timestamp": now.isoformat(),
        "ticker": signal["ticker"],
        "name": signal.get("name", ""),
        "type": signal.get("type", ""),
        "direction": signal["direction"],
        "signal_type": signal.get("signal_type", ""),
        "signal_score": signal.get("signal_score", 0),
        "entry": signal["entry"],
        "stop_loss": signal["stop_loss"],
        "tp1": signal["tp1"],
        "tp2": signal["tp2"],
        "lot_size": signal.get("lot_size", 0),
        "atr": signal.get("atr", 0),
        "rsi": signal.get("rsi", 0),
        "adx": signal.get("adx"),
        "vol_ratio": signal.get("vol_ratio"),
        "trend": signal.get("trend", ""),
        # Tracking fields
        "status": "ACTIVE",           # ACTIVE / TP1_HIT / TP2_HIT / SL_HIT / EXPIRED
        "tp1_hit": False,
        "tp1_hit_time": None,
        "tp2_hit": False,
        "tp2_hit_time": None,
        "sl_hit": False,
        "sl_hit_time": None,
        "current_price": signal["entry"],
        "highest_price": signal["entry"],  # For BUY: highest seen
        "lowest_price": signal["entry"],   # For SELL: lowest seen
        "max_favorable": 0.0,             # Max profit seen (in price units)
        "max_adverse": 0.0,               # Max drawdown seen (in price units)
        "last_checked": now.isoformat(),
        "checks_count": 0,
        "pnl_at_close": None,
    }

    active.append(tracked)
    _save_json(ACTIVE_FILE, active)
    print(f"  [TRACKER] Logged signal {signal_id}: {signal['direction']} {signal['name']}")
    return signal_id


def get_active_signals():
    """Get all currently active (unresolved) signals."""
    return [s for s in _load_json(ACTIVE_FILE) if s["status"] == "ACTIVE"]


def get_all_tracked():
    """Get ALL tracked signals (active + resolved)."""
    return _load_json(ACTIVE_FILE)


def update_signal(signal_id, updates):
    """Update a tracked signal by ID."""
    active = _load_json(ACTIVE_FILE)
    for sig in active:
        if sig["signal_id"] == signal_id:
            sig.update(updates)
            break
    _save_json(ACTIVE_FILE, active)


def archive_resolved():
    """
    Move resolved signals from active to history.
    Call this during weekly report generation.
    """
    active = _load_json(ACTIVE_FILE)
    history = _load_json(HISTORY_FILE)

    still_active = []
    for sig in active:
        if sig["status"] != "ACTIVE":
            history.append(sig)
        else:
            still_active.append(sig)

    _save_json(ACTIVE_FILE, still_active)
    _save_json(HISTORY_FILE, history)
    return len(active) - len(still_active)


def get_signals_for_period(days=7):
    """Get all signals (active + history) from the last N days."""
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    all_signals = _load_json(ACTIVE_FILE) + _load_json(HISTORY_FILE)

    result = []
    for sig in all_signals:
        try:
            ts = datetime.fromisoformat(sig["timestamp"]).timestamp()
            if ts >= cutoff:
                result.append(sig)
        except (ValueError, KeyError):
            continue

    # Deduplicate by signal_id
    seen = set()
    unique = []
    for sig in result:
        if sig["signal_id"] not in seen:
            seen.add(sig["signal_id"])
            unique.append(sig)

    return unique


def get_log_stats():
    """Quick stats for debugging."""
    active = _load_json(ACTIVE_FILE)
    history = _load_json(HISTORY_FILE)
    active_count = sum(1 for s in active if s["status"] == "ACTIVE")
    resolved = sum(1 for s in active if s["status"] != "ACTIVE")
    return {
        "active": active_count,
        "resolved_pending": resolved,
        "archived": len(history),
        "total": active_count + resolved + len(history),
    }


RUN_LOG_FILE = LOG_DIR / "run_log.json"
MAX_RUN_LOG_ENTRIES = 200  # Keep last 200 runs


def log_run_summary(summary):
    """
    Append a run summary to run_log.json.
    Called at end of each cmd_check_signals() run.
    Keeps last 200 entries max.
    """
    entries = _load_json(RUN_LOG_FILE) if RUN_LOG_FILE.exists() else []
    entries.append(summary)
    # Trim to last 200
    if len(entries) > MAX_RUN_LOG_ENTRIES:
        entries = entries[-MAX_RUN_LOG_ENTRIES:]
    _save_json(RUN_LOG_FILE, entries)


def get_open_signals():
    """
    Get signals that still need price tracking:
    ACTIVE signals + TP1_HIT signals (still open, waiting for TP2 or SL).
    """
    return [s for s in _load_json(ACTIVE_FILE) if s["status"] in ("ACTIVE", "TP1_HIT")]
