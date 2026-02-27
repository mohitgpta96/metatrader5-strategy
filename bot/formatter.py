"""
Telegram message formatter.
Formats trading signals into clean, readable Telegram messages.
"""


def format_signal(signal):
    """Format a single trading signal for Telegram."""
    sig_type = signal["type"]
    is_global_commodity = sig_type == "commodity"
    currency = "$" if is_global_commodity else "Rs "

    direction_label = "BUY" if signal["direction"] == "BUY" else "SELL"
    name = signal['name']
    if sig_type == "stock":
        name = f"{name} FUT"

    lines = [
        f"{direction_label} SIGNAL -- {name}",
        "=" * 35,
        f"Entry:     {currency}{signal['entry']:,.2f}",
        f"Stop Loss: {currency}{signal['stop_loss']:,.2f}",
        f"TP1:       {currency}{signal['tp1']:,.2f}",
        f"TP2:       {currency}{signal['tp2']:,.2f}",
        "=" * 35,
        f"Lot Size:  {signal['lot_size']} {'lots' if is_global_commodity else 'units'}",
        f"Max Loss:  {currency}{signal['potential_loss']:,.2f}",
    ]

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
