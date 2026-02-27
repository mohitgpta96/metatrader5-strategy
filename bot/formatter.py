"""
Telegram message formatter.
Formats trading signals into clean, readable Telegram messages.
"""


def format_signal(signal):
    """Format a single trading signal for Telegram."""
    sig_type = signal["type"]
    is_global_commodity = sig_type == "commodity"
    is_mcx = sig_type == "mcx_commodity"
    currency = "$" if is_global_commodity else "Rs "

    direction_label = "BUY" if signal["direction"] == "BUY" else "SELL"

    sl_diff = signal["sl_distance"]
    tp1_diff = abs(signal["tp1"] - signal["entry"])
    tp2_diff = abs(signal["tp2"] - signal["entry"])

    # Name with market label
    name = signal['name']
    if sig_type == "stock":
        name = f"{name} FUT"

    lines = [
        f"{direction_label} SIGNAL -- {name}",
        "=" * 35,
        f"Entry:     {currency}{signal['entry']:,.2f}",
        f"Stop Loss: {currency}{signal['stop_loss']:,.2f} (-{currency}{sl_diff:,.2f})",
        f"TP1:       {currency}{signal['tp1']:,.2f} (+{currency}{tp1_diff:,.2f}) [1:{signal['rr_tp1']}]",
        f"TP2:       {currency}{signal['tp2']:,.2f} (+{currency}{tp2_diff:,.2f}) [1:{signal['rr_tp2']}]",
        "=" * 35,
    ]

    if is_global_commodity:
        from config.settings import ACCOUNT_BALANCE, RISK_PERCENT
        lines.extend([
            f"Account: ${ACCOUNT_BALANCE:,.0f} | Risk: {RISK_PERCENT}%",
            f"Lot Size: {signal['lot_size']} lots",
            f"Max Loss: ${signal['potential_loss']:,.2f}",
            f"TP1 Gain: ${signal['potential_tp1']:,.2f}",
        ])
    else:
        lines.extend([
            f"Qty: {signal['lot_size']} units",
            f"Max Loss: {currency}{signal['potential_loss']:,.2f}",
            f"TP1 Gain: {currency}{signal['potential_tp1']:,.2f}",
        ])

    lines.extend([
        "=" * 35,
        f"EMA20 {'>' if signal['direction'] == 'BUY' else '<'} EMA50 | RSI: {signal['rsi']}",
        f"Trend: {signal['trend']} | ATR: {currency}{signal['atr']:,.2f}",
        f"Signal Type: {signal.get('signal_type', '?')} | Score: {signal.get('signal_score', '?')}/10",
    ])

    # --- Real-time Market Context ---
    macro_warning = signal.get("macro_warning")
    macro_risk = signal.get("macro_risk", "MEDIUM")
    macro_outlook = signal.get("macro_outlook", "NEUTRAL")
    geo_events = signal.get("geo_events", [])
    top_news = signal.get("top_news")

    has_context = (
        macro_warning
        or macro_risk in ("HIGH", "EXTREME")
        or geo_events
    )

    if has_context:
        lines.append("=" * 35)
        lines.append(f"MARKET CONTEXT (Real-time):")
        lines.append(f"Risk: {macro_risk} | Outlook: {macro_outlook}")
        if macro_warning:
            lines.append(f"[!] {macro_warning}")
        for ev in geo_events:
            lines.append(f">> {ev}")

    lines.extend([
        "=" * 35,
        "Analysis only, NOT financial advice.",
    ])

    if signal.get("was_capped"):
        lines.insert(-1, "[!] Lot size was capped for safety.")

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
