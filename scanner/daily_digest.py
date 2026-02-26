"""
Daily digest generator.
Creates a summary of all markets for Telegram.
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scanner.market_scanner import scan_all


def generate_digest():
    """Generate a complete daily market digest."""
    results = scan_all()

    today = datetime.now().strftime("%b %d, %Y")
    lines = []
    lines.append(f"DAILY MARKET DIGEST -- {today}")
    lines.append("=" * 40)

    # --- Commodities ---
    lines.append("")
    lines.append("COMMODITY FUTURES")
    lines.append("-" * 30)
    for status in results["commodity_statuses"]:
        emoji = _condition_emoji(status["condition"])
        lines.append(f"{emoji} {status['name']}: ${status['close']}")
        lines.append(f"   Trend: {status['trend']} | RSI: {status['rsi']} | {status['condition']}")

    # Commodity signals
    for signal in results["commodity_signals"]:
        direction_emoji = "BUY" if signal["direction"] == "BUY" else "SELL"
        lines.append(f"\n   >> {direction_emoji} SIGNAL: {signal['name']}")
        lines.append(f"   Entry: ${signal['entry']} | SL: ${signal['stop_loss']} | TP1: ${signal['tp1']}")
        lines.append(f"   Lot: {signal['lot_size']} | Loss: ${signal['potential_loss']} | Gain: ${signal['potential_tp1']}")

    # --- Indices ---
    lines.append("")
    lines.append("INDEX FUTURES")
    lines.append("-" * 30)
    for status in results["index_statuses"]:
        emoji = _condition_emoji(status["condition"])
        lines.append(f"{emoji} {status['name']}: {status['close']}")
        lines.append(f"   Trend: {status['trend']} | RSI: {status['rsi']}")

    # --- Stock Signals ---
    buy_signals = [s for s in results["stock_signals"] if s["direction"] == "BUY"]
    sell_signals = [s for s in results["stock_signals"] if s["direction"] == "SELL"]

    lines.append("")
    lines.append(f"STOCK FUTURES ({len(buy_signals)} BUY, {len(sell_signals)} SELL)")
    lines.append("-" * 30)

    if buy_signals:
        lines.append("\nBUY Signals:")
        for s in buy_signals[:10]:  # Top 10
            lines.append(f"  >> {s['name']} @ Rs {s['entry']} | SL: Rs {s['stop_loss']} | TP1: Rs {s['tp1']}")
            lines.append(f"     RSI: {s['rsi']} | Lot: {s['lot_size']} | R:R 1:{s['rr_tp2']}")

    if sell_signals:
        lines.append("\nSELL Signals:")
        for s in sell_signals[:10]:
            lines.append(f"  >> {s['name']} @ Rs {s['entry']} | SL: Rs {s['stop_loss']} | TP1: Rs {s['tp1']}")
            lines.append(f"     RSI: {s['rsi']} | Lot: {s['lot_size']} | R:R 1:{s['rr_tp2']}")

    if not buy_signals and not sell_signals:
        lines.append("  No active stock signals today.")

    # --- Top Overbought / Oversold ---
    stock_statuses = results["stock_statuses"]
    if stock_statuses:
        overbought = sorted(
            [s for s in stock_statuses if s["rsi"] and s["rsi"] > 65],
            key=lambda x: x["rsi"],
            reverse=True,
        )[:5]
        oversold = sorted(
            [s for s in stock_statuses if s["rsi"] and s["rsi"] < 35],
            key=lambda x: x["rsi"],
        )[:5]

        if overbought:
            lines.append("\nOVERBOUGHT (potential sell candidates):")
            for s in overbought:
                lines.append(f"  {s['name']}: Rs {s['close']} (RSI: {s['rsi']})")

        if oversold:
            lines.append("\nOVERSOLD (potential buy candidates):")
            for s in oversold:
                lines.append(f"  {s['name']}: Rs {s['close']} (RSI: {s['rsi']})")

    lines.append("")
    lines.append("=" * 40)
    lines.append("Analysis only, NOT financial advice.")

    return "\n".join(lines)


def _condition_emoji(condition):
    mapping = {
        "STRONG BULLISH": "[STRONG UP]",
        "BULLISH": "[UP]",
        "NEUTRAL": "[--]",
        "BEARISH": "[DOWN]",
        "STRONG BEARISH": "[STRONG DOWN]",
        "OVERBOUGHT": "[OVERBOUGHT]",
        "OVERSOLD": "[OVERSOLD]",
    }
    return mapping.get(condition, "[--]")


if __name__ == "__main__":
    digest = generate_digest()
    print(digest)
