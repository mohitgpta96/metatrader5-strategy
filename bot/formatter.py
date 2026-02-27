"""
Telegram message formatter.
Formats trading signals into clean, readable Telegram messages.
"""


def _format_exit_plan(lot_size, has_tp3, is_commodity):
    """
    Compute the position exit plan string.
    Without TP3 : 50% @ TP1 → 50% @ TP2
    With TP3    : 50% @ TP1 → 40% @ TP2 → 10% @ TP3 (runner)
    Shows actual lot/unit quantities where meaningful.
    Falls back to percentages when lot is too small to split.
    """
    unit = "L" if is_commodity else "u"

    if has_tp3:
        tp1_raw, tp2_raw, tp3_raw = lot_size * 0.50, lot_size * 0.40, lot_size * 0.10
    else:
        tp1_raw, tp2_raw, tp3_raw = lot_size * 0.50, lot_size * 0.50, None

    if is_commodity:
        tp1 = round(tp1_raw, 2)
        tp2 = round(tp2_raw, 2)
        tp3 = round(tp3_raw, 2) if tp3_raw is not None else None
        min_q = 0.01
        fmt = lambda x: f"{x:.2f}{unit}"
    else:
        tp1 = round(tp1_raw)
        tp2 = round(tp2_raw)
        tp3 = round(tp3_raw) if tp3_raw is not None else None
        min_q = 1
        fmt = lambda x: f"{int(x)}{unit}"

    can_split = tp1 >= min_q and tp2 >= min_q and (tp1 + tp2) <= lot_size

    if not can_split:
        # Lot too small to split — show percentages only
        if has_tp3:
            return "50% @ TP1 → 40% @ TP2 → 10% @ TP3"
        return "50% @ TP1 → 50% @ TP2"

    if has_tp3:
        tp3_str = fmt(tp3) if (tp3 is not None and tp3 >= min_q) else "10%"
        return f"{fmt(tp1)} @ TP1 → {fmt(tp2)} @ TP2 → {tp3_str} @ TP3"
    return f"{fmt(tp1)} @ TP1 → {fmt(tp2)} @ TP2"


def format_signal(signal):
    """Format a single trading signal for Telegram."""
    sig_type = signal["type"]
    is_global_commodity = sig_type == "commodity"
    currency = "$" if is_global_commodity else "Rs "

    direction_label = "BUY" if signal["direction"] == "BUY" else "SELL"
    name = signal['name']
    if sig_type == "stock":
        name = f"{name} FUT"

    has_tp3 = signal.get("tp3") is not None

    lines = [
        f"{direction_label} SIGNAL -- {name}",
        f"Type: {signal.get('signal_type', 'Signal')}",
        "=" * 35,
        f"Entry:     {currency}{signal['entry']:,.2f}",
        f"Stop Loss: {currency}{signal['stop_loss']:,.2f}",
        f"TP1:       {currency}{signal['tp1']:,.2f}",
        f"TP2:       {currency}{signal['tp2']:,.2f}",
    ]
    if has_tp3:
        lines.append(f"TP3 Runner:{currency}{signal['tp3']:,.2f}")
    entry_type = signal.get("entry_type", "MARKET")
    if entry_type == "LIMIT":
        entry_label = f"Limit Order — wait for price at {currency}{signal['entry']:,.2f}"
    else:
        entry_label = "Market Order (execute at open of next bar)"

    lines += [
        "=" * 35,
        f"Lot Size:  {signal['lot_size']} {'lots' if is_global_commodity else 'units'}",
        f"Entry:     {entry_label}",
        f"Exit Plan: {_format_exit_plan(signal['lot_size'], has_tp3, is_global_commodity)}",
        f"SL Rule:   Move SL to Entry after TP1 hits",
        f"Max Loss:  {currency}{signal['potential_loss']:,.2f}",
    ]
    rr = signal.get("rr_tp2")
    if rr is not None:
        lines.append(f"R:R Ratio: 1:{rr:.1f}")

    return "\n".join(lines)


def format_status(status):
    """Format a market status for daily digest."""
    is_commodity = status["type"] == "commodity"
    currency = "$" if is_commodity else "Rs "

    return (
        f"{status['name']}: {currency}{status['close']:,.2f} -- {status['condition']}\n"
        f"  Trend: {status['trend']} | RSI: {status['rsi']}"
    )


def format_multiple_signals(signals):
    """Format multiple signals into one message."""
    if not signals:
        return "No active signals at this time."

    messages = []
    for i, signal in enumerate(signals, 1):
        messages.append(f"--- Signal {i}/{len(signals)} ---\n")
        messages.append(format_signal(signal))
        messages.append("")

    return "\n".join(messages)


if __name__ == "__main__":
    # Test with sample data
    sample_signal = {
        "ticker": "GC=F",
        "name": "Gold (XAUUSD)",
        "type": "commodity",
        "direction": "BUY",
        "entry": 5140.00,
        "stop_loss": 5102.50,
        "tp1": 5190.00,
        "tp2": 5215.00,
        "lot_size": 0.03,
        "atr": 25.00,
        "rsi": 52.3,
        "ema_fast": 5135.00,
        "ema_slow": 5120.00,
        "trend": "Bullish",
        "rr_tp1": 1.33,
        "rr_tp2": 2.0,
        "potential_loss": 112.50,
        "potential_tp1": 150.00,
        "potential_tp2": 225.00,
        "sl_distance": 37.50,
        "was_capped": False,
    }

    print(format_signal(sample_signal))
