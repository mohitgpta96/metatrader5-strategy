"""
Weekly Performance Report Generator.
Analyzes all signals from the past 7 days and generates a detailed report.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tracker.signal_logger import get_signals_for_period, archive_resolved


def generate_weekly_report(days=7):
    """
    Generate a comprehensive 7-day performance report.
    Returns: (report_text, report_data)
    """
    signals = get_signals_for_period(days=days)

    if not signals:
        report = (
            "WEEKLY PERFORMANCE REPORT\n"
            "=" * 40 + "\n"
            f"Period: Last {days} days\n"
            "=" * 40 + "\n\n"
            "No signals were generated this week.\n"
            "Markets may have been quiet or filters rejected all setups."
        )
        return report, {"total": 0}

    # Classify signals
    resolved = [s for s in signals if s["status"] != "ACTIVE"]
    still_active = [s for s in signals if s["status"] == "ACTIVE"]

    tp1_wins = [s for s in resolved if s["status"] == "TP1_HIT"]
    tp2_wins = [s for s in resolved if s["status"] == "TP2_HIT"]
    sl_losses = [s for s in resolved if s["status"] == "SL_HIT"]
    expired = [s for s in resolved if s["status"] == "EXPIRED"]

    total_resolved = len(resolved)
    total_wins = len(tp1_wins) + len(tp2_wins)
    total_losses = len(sl_losses)
    win_rate = (total_wins / total_resolved * 100) if total_resolved > 0 else 0

    # P&L calculations
    total_pnl_points = sum(s.get("pnl_at_close", 0) for s in resolved)
    winning_pnl = sum(s.get("pnl_at_close", 0) for s in resolved if s.get("pnl_at_close", 0) > 0)
    losing_pnl = abs(sum(s.get("pnl_at_close", 0) for s in resolved if s.get("pnl_at_close", 0) < 0))
    profit_factor = (winning_pnl / losing_pnl) if losing_pnl > 0 else float("inf")

    avg_win = winning_pnl / total_wins if total_wins > 0 else 0
    avg_loss = losing_pnl / total_losses if total_losses > 0 else 0

    # By instrument type
    by_type = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0, "total": 0})
    for s in resolved:
        t = s.get("type", "unknown")
        by_type[t]["total"] += 1
        pnl = s.get("pnl_at_close", 0)
        by_type[t]["pnl"] += pnl
        if pnl > 0:
            by_type[t]["wins"] += 1
        else:
            by_type[t]["losses"] += 1

    # By ticker
    by_ticker = defaultdict(lambda: {"wins": 0, "losses": 0, "pnl": 0, "total": 0, "name": ""})
    for s in resolved:
        tk = s["ticker"]
        by_ticker[tk]["name"] = s.get("name", tk)
        by_ticker[tk]["total"] += 1
        pnl = s.get("pnl_at_close", 0)
        by_ticker[tk]["pnl"] += pnl
        if pnl > 0:
            by_ticker[tk]["wins"] += 1
        else:
            by_ticker[tk]["losses"] += 1

    # By direction
    buy_signals = [s for s in resolved if s["direction"] == "BUY"]
    sell_signals = [s for s in resolved if s["direction"] == "SELL"]
    buy_wins = sum(1 for s in buy_signals if s.get("pnl_at_close", 0) > 0)
    sell_wins = sum(1 for s in sell_signals if s.get("pnl_at_close", 0) > 0)

    # By signal type (EMA Crossover vs Pullback)
    by_sig_type = defaultdict(lambda: {"wins": 0, "losses": 0, "total": 0})
    for s in resolved:
        st = s.get("signal_type", "Unknown")
        by_sig_type[st]["total"] += 1
        if s.get("pnl_at_close", 0) > 0:
            by_sig_type[st]["wins"] += 1
        else:
            by_sig_type[st]["losses"] += 1

    # Best and worst signals
    best = max(resolved, key=lambda s: s.get("pnl_at_close", 0)) if resolved else None
    worst = min(resolved, key=lambda s: s.get("pnl_at_close", 0)) if resolved else None

    # Signal score analysis
    scores = [s.get("signal_score", 0) for s in resolved if s.get("signal_score")]
    avg_score = sum(scores) / len(scores) if scores else 0
    win_scores = [s.get("signal_score", 0) for s in resolved if s.get("pnl_at_close", 0) > 0 and s.get("signal_score")]
    loss_scores = [s.get("signal_score", 0) for s in resolved if s.get("pnl_at_close", 0) <= 0 and s.get("signal_score")]
    avg_win_score = sum(win_scores) / len(win_scores) if win_scores else 0
    avg_loss_score = sum(loss_scores) / len(loss_scores) if loss_scores else 0

    # Max favorable / adverse excursion
    avg_mfe = sum(s.get("max_favorable", 0) for s in resolved) / total_resolved if total_resolved else 0
    avg_mae = sum(s.get("max_adverse", 0) for s in resolved) / total_resolved if total_resolved else 0

    # Build report
    now = datetime.now(timezone.utc)
    type_labels = {
        "commodity": "Global Commodities",
        "mcx_commodity": "MCX Commodities",
        "stock": "Indian Stocks",
        "index": "Indices",
    }

    lines = [
        "7-DAY LIVE PERFORMANCE REPORT",
        "=" * 40,
        f"Generated: {now.strftime('%d %b %Y, %I:%M %p')} UTC",
        f"Period: Last {days} days",
        "=" * 40,
        "",
        "OVERALL SUMMARY",
        "-" * 35,
        f"Total Signals:    {len(signals)}",
        f"Resolved:         {total_resolved}",
        f"Still Active:     {len(still_active)}",
        "",
        f"Wins (TP1+TP2):   {total_wins}  ({len(tp1_wins)} TP1 + {len(tp2_wins)} TP2)",
        f"Losses (SL):      {total_losses}",
        f"Expired:          {len(expired)}",
        f"WIN RATE:         {win_rate:.1f}%",
        "",
        f"Profit Factor:    {profit_factor:.2f}" if profit_factor != float("inf") else "Profit Factor:    INF (no losses!)",
        f"Net P&L (points): {total_pnl_points:+.2f}",
        f"Avg Win:          +{avg_win:.2f}",
        f"Avg Loss:         -{avg_loss:.2f}",
        "",
    ]

    # Direction breakdown
    lines.extend([
        "BY DIRECTION",
        "-" * 35,
        f"BUY:  {len(buy_signals)} trades, {buy_wins} wins ({buy_wins/len(buy_signals)*100:.0f}%)" if buy_signals else "BUY:  0 trades",
        f"SELL: {len(sell_signals)} trades, {sell_wins} wins ({sell_wins/len(sell_signals)*100:.0f}%)" if sell_signals else "SELL: 0 trades",
        "",
    ])

    # By market type
    if by_type:
        lines.extend([
            "BY MARKET",
            "-" * 35,
        ])
        for t, data in sorted(by_type.items()):
            label = type_labels.get(t, t)
            wr = data["wins"] / data["total"] * 100 if data["total"] > 0 else 0
            lines.append(f"{label}: {data['total']} trades | {wr:.0f}% win | P&L: {data['pnl']:+.2f}")
        lines.append("")

    # By signal type
    if by_sig_type:
        lines.extend([
            "BY SIGNAL TYPE",
            "-" * 35,
        ])
        for st, data in sorted(by_sig_type.items()):
            wr = data["wins"] / data["total"] * 100 if data["total"] > 0 else 0
            lines.append(f"{st}: {data['total']} trades | {wr:.0f}% win")
        lines.append("")

    # Top instruments
    if by_ticker:
        lines.extend([
            "BY INSTRUMENT",
            "-" * 35,
        ])
        sorted_tickers = sorted(by_ticker.items(), key=lambda x: x[1]["pnl"], reverse=True)
        for tk, data in sorted_tickers:
            wr = data["wins"] / data["total"] * 100 if data["total"] > 0 else 0
            lines.append(f"{data['name']}: {data['total']} trades | {wr:.0f}% win | P&L: {data['pnl']:+.2f}")
        lines.append("")

    # Signal score analysis
    if scores:
        lines.extend([
            "SIGNAL SCORE ANALYSIS",
            "-" * 35,
            f"Avg Score (all):    {avg_score:.1f}/10",
            f"Avg Score (wins):   {avg_win_score:.1f}/10",
            f"Avg Score (losses): {avg_loss_score:.1f}/10",
            "",
        ])

    # Max excursion analysis
    lines.extend([
        "EXCURSION ANALYSIS",
        "-" * 35,
        f"Avg Max Favorable: {avg_mfe:.2f} (how far price moved in our favor)",
        f"Avg Max Adverse:   {avg_mae:.2f} (how far price moved against us)",
        "",
    ])

    # Best / Worst
    if best:
        lines.extend([
            "BEST & WORST TRADES",
            "-" * 35,
            f"Best:  {best['name']} {best['direction']} | P&L: {best.get('pnl_at_close', 0):+.2f} | Score: {best.get('signal_score', 'N/A')}",
        ])
    if worst:
        lines.append(
            f"Worst: {worst['name']} {worst['direction']} | P&L: {worst.get('pnl_at_close', 0):+.2f} | Score: {worst.get('signal_score', 'N/A')}"
        )
        lines.append("")

    # Individual trade log
    lines.extend([
        "TRADE LOG",
        "-" * 35,
    ])
    for s in sorted(signals, key=lambda x: x["timestamp"]):
        ts = s["timestamp"][:16].replace("T", " ")
        pnl = s.get("pnl_at_close")
        pnl_str = f"{pnl:+.2f}" if pnl is not None else "Open"
        status = s["status"]
        emoji = {"TP1_HIT": "W", "TP2_HIT": "W", "SL_HIT": "L", "EXPIRED": "X", "ACTIVE": "..."}
        lines.append(
            f"[{emoji.get(status, '?')}] {ts} | {s['direction']:4} {s['name'][:18]:<18} | {status:8} | P&L: {pnl_str}"
        )
    lines.append("")

    # Still active signals
    if still_active:
        lines.extend([
            "STILL ACTIVE (monitoring)",
            "-" * 35,
        ])
        for s in still_active:
            entry = s["entry"]
            curr = s.get("current_price", entry)
            if s["direction"] == "BUY":
                unrealized = curr - entry
            else:
                unrealized = entry - curr
            lines.append(
                f"  {s['direction']:4} {s['name'][:20]:<20} Entry: {entry:.2f} | Now: {curr:.2f} | Unrealized: {unrealized:+.2f}"
            )
        lines.append("")

    # Verdict
    lines.extend([
        "=" * 40,
        "VERDICT",
        "=" * 40,
    ])
    if total_resolved == 0:
        lines.append("No resolved trades yet. Keep monitoring.")
    elif win_rate >= 70 and profit_factor >= 2.0:
        lines.append("EXCELLENT! Strategy performing well.")
        lines.append("Filters are working. Continue with same settings.")
    elif win_rate >= 55 and profit_factor >= 1.3:
        lines.append("GOOD. Strategy has a positive edge.")
        lines.append("Consider keeping current filters.")
    elif win_rate >= 45 and profit_factor >= 1.0:
        lines.append("AVERAGE. Strategy is marginally profitable.")
        lines.append("May need tighter filters or higher MIN_SIGNAL_SCORE.")
    else:
        lines.append("NEEDS WORK. Strategy is currently losing.")
        lines.append("Consider: Higher ADX threshold, higher MIN_SIGNAL_SCORE,")
        lines.append("or avoiding certain instruments/directions.")
    lines.append("")

    # Suggestions based on data
    suggestions = _generate_suggestions(
        win_rate, profit_factor, by_type, by_sig_type,
        buy_signals, sell_signals, buy_wins, sell_wins,
        avg_win_score, avg_loss_score, avg_mfe, avg_mae,
    )
    if suggestions:
        lines.extend([
            "IMPROVEMENT SUGGESTIONS",
            "-" * 35,
        ])
        for i, sug in enumerate(suggestions, 1):
            lines.append(f"{i}. {sug}")
        lines.append("")

    lines.append("=" * 40)
    lines.append("Analysis only, NOT financial advice.")

    report = "\n".join(lines)

    report_data = {
        "total": len(signals),
        "resolved": total_resolved,
        "active": len(still_active),
        "wins": total_wins,
        "losses": total_losses,
        "expired": len(expired),
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "INF",
        "net_pnl_points": round(total_pnl_points, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "best_trade": best["signal_id"] if best else None,
        "worst_trade": worst["signal_id"] if worst else None,
        "by_type": dict(by_type),
        "by_ticker": dict(by_ticker),
    }

    return report, report_data


def _generate_suggestions(win_rate, pf, by_type, by_sig_type,
                          buy_signals, sell_signals, buy_wins, sell_wins,
                          avg_win_score, avg_loss_score, avg_mfe, avg_mae):
    """Generate actionable improvement suggestions based on data."""
    suggestions = []

    # Direction imbalance
    if buy_signals and sell_signals:
        buy_wr = buy_wins / len(buy_signals) * 100
        sell_wr = sell_wins / len(sell_signals) * 100
        if buy_wr > sell_wr + 20:
            suggestions.append(f"BUY signals ({buy_wr:.0f}% win) outperform SELL ({sell_wr:.0f}%). Consider focusing on BUY-only in current market.")
        elif sell_wr > buy_wr + 20:
            suggestions.append(f"SELL signals ({sell_wr:.0f}% win) outperform BUY ({buy_wr:.0f}%). Market may be in a downtrend.")

    # Signal score gap
    if avg_win_score and avg_loss_score:
        if avg_win_score > avg_loss_score + 1:
            suggestions.append(f"Winning trades have avg score {avg_win_score:.1f} vs losing {avg_loss_score:.1f}. Consider raising MIN_SIGNAL_SCORE to {int(avg_loss_score + 1)}.")

    # Excursion analysis
    if avg_mfe > 0 and avg_mae > 0:
        if avg_mae > avg_mfe * 0.8:
            suggestions.append("Price moves significantly against entries. Consider tighter entry timing or waiting for confirmation.")
        if avg_mfe > avg_mae * 3:
            suggestions.append("Favorable excursions are much larger than adverse. TP targets could be widened for more profit.")

    # Market type performance
    for t, data in by_type.items():
        if data["total"] >= 3:
            wr = data["wins"] / data["total"] * 100
            if wr < 40:
                labels = {"commodity": "Commodities", "mcx_commodity": "MCX", "stock": "Indian Stocks"}
                suggestions.append(f"{labels.get(t, t)} has low win rate ({wr:.0f}%). Consider skipping or using stricter filters.")

    # Signal type analysis
    for st, data in by_sig_type.items():
        if data["total"] >= 3:
            wr = data["wins"] / data["total"] * 100
            if wr < 40:
                suggestions.append(f"'{st}' signal type has {wr:.0f}% win rate. May need parameter adjustment.")

    # General
    if win_rate < 50:
        suggestions.append("Overall win rate below 50%. Consider: higher ADX threshold (25+), higher signal score (7+), or reducing pullback signals.")

    if not suggestions:
        suggestions.append("Strategy performing within expectations. Continue monitoring.")

    return suggestions[:5]  # Max 5 suggestions


if __name__ == "__main__":
    print("Generating weekly report...\n")
    report, data = generate_weekly_report()
    print(report)
