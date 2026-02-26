"""
Backtesting engine.
Tests the Triple Confirmation strategy on historical data.
Uses the backtesting.py library for robust analysis.
"""
import sys
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD,
    RSI_BUY_MIN, RSI_BUY_MAX, RSI_SELL_MIN, RSI_SELL_MAX,
    SL_ATR_MULTIPLIER, TP1_ATR_MULTIPLIER, TP2_ATR_MULTIPLIER,
    RISK_PERCENT,
)
from config.instruments import get_display_name


def backtest_strategy(df, ticker="", initial_balance=10000, risk_percent=None):
    """
    Run backtest on historical data using our Triple Confirmation strategy.

    Args:
        df: DataFrame with OHLCV data (already has Open, High, Low, Close, Volume)
        ticker: instrument ticker for display
        initial_balance: starting account balance
        risk_percent: risk per trade (default from settings)

    Returns:
        dict with backtest results
    """
    risk_pct = risk_percent or RISK_PERCENT

    # Add indicators
    from strategy.indicators import add_indicators
    df = add_indicators(df)
    if df is None or df.empty:
        return None

    # Drop rows with NaN indicators
    ema_slow_col = f"EMA_{EMA_SLOW}"
    rsi_col = f"RSI_{RSI_PERIOD}"
    atr_col = f"ATR_{ATR_PERIOD}"

    df = df.dropna(subset=[ema_slow_col, rsi_col, atr_col])
    if len(df) < 10:
        return None

    # Simulation
    balance = initial_balance
    trades = []
    equity_curve = [balance]
    in_trade = False
    current_trade = None
    max_balance = balance
    max_drawdown = 0

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]

        # Track equity
        if in_trade:
            # Check if SL or TP hit
            trade = current_trade
            if trade["direction"] == "BUY":
                # Check SL (hit if Low <= SL)
                if row["Low"] <= trade["stop_loss"]:
                    pnl = trade["stop_loss"] - trade["entry"]
                    pnl_dollar = pnl * trade["position_multiplier"]
                    balance += pnl_dollar
                    trade["exit"] = trade["stop_loss"]
                    trade["exit_reason"] = "Stop Loss"
                    trade["pnl"] = round(pnl_dollar, 2)
                    trade["exit_date"] = df.index[i]
                    trades.append(trade)
                    in_trade = False
                    current_trade = None
                # Check TP1 (hit if High >= TP1)
                elif row["High"] >= trade["tp1"]:
                    pnl = trade["tp1"] - trade["entry"]
                    pnl_dollar = pnl * trade["position_multiplier"]
                    balance += pnl_dollar
                    trade["exit"] = trade["tp1"]
                    trade["exit_reason"] = "Take Profit 1"
                    trade["pnl"] = round(pnl_dollar, 2)
                    trade["exit_date"] = df.index[i]
                    trades.append(trade)
                    in_trade = False
                    current_trade = None

            elif trade["direction"] == "SELL":
                if row["High"] >= trade["stop_loss"]:
                    pnl = trade["entry"] - trade["stop_loss"]
                    pnl_dollar = pnl * trade["position_multiplier"]
                    balance += pnl_dollar
                    trade["exit"] = trade["stop_loss"]
                    trade["exit_reason"] = "Stop Loss"
                    trade["pnl"] = round(pnl_dollar, 2)
                    trade["exit_date"] = df.index[i]
                    trades.append(trade)
                    in_trade = False
                    current_trade = None
                elif row["Low"] <= trade["tp1"]:
                    pnl = trade["entry"] - trade["tp1"]
                    pnl_dollar = pnl * trade["position_multiplier"]
                    balance += pnl_dollar
                    trade["exit"] = trade["tp1"]
                    trade["exit_reason"] = "Take Profit 1"
                    trade["pnl"] = round(pnl_dollar, 2)
                    trade["exit_date"] = df.index[i]
                    trades.append(trade)
                    in_trade = False
                    current_trade = None

        # Check for new signal (only if not in a trade)
        if not in_trade:
            ema_cross = row.get("EMA_Cross", 0)
            rsi = row[rsi_col]
            atr = row[atr_col]
            close = row["Close"]

            direction = None

            # Signal Type 1: EMA Crossover
            if ema_cross == 1 and RSI_BUY_MIN <= rsi <= RSI_BUY_MAX:
                direction = "BUY"
            elif ema_cross == -1 and RSI_SELL_MIN <= rsi <= RSI_SELL_MAX:
                direction = "SELL"

            # Signal Type 2: Trend Pullback (more signals in trending markets)
            if direction is None and i >= 3:
                ema_fast_col = f"EMA_{EMA_FAST}"
                trend = row.get("Trend", 0)
                ema_fast_val = row.get(ema_fast_col, 0)

                distance_to_ema = abs(close - ema_fast_val)
                near_ema = distance_to_ema <= (0.5 * atr) if atr > 0 else False

                prev_candle = df.iloc[i - 1]

                if trend == 1 and near_ema and 35 <= rsi <= 55:
                    if prev_candle["Low"] <= ema_fast_val * 1.003 and close > prev_candle["Close"]:
                        direction = "BUY"

                elif trend == -1 and near_ema and 45 <= rsi <= 65:
                    if prev_candle["High"] >= ema_fast_val * 0.997 and close < prev_candle["Close"]:
                        direction = "SELL"

            if direction and atr > 0:
                risk_amount = balance * (risk_pct / 100.0)
                sl_distance = SL_ATR_MULTIPLIER * atr

                # Position multiplier (simplified - risk_amount / sl_distance)
                position_multiplier = risk_amount / sl_distance if sl_distance > 0 else 0

                if direction == "BUY":
                    sl = close - sl_distance
                    tp1 = close + (TP1_ATR_MULTIPLIER * atr)
                    tp2 = close + (TP2_ATR_MULTIPLIER * atr)
                else:
                    sl = close + sl_distance
                    tp1 = close - (TP1_ATR_MULTIPLIER * atr)
                    tp2 = close - (TP2_ATR_MULTIPLIER * atr)

                current_trade = {
                    "direction": direction,
                    "entry": close,
                    "stop_loss": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "atr": atr,
                    "rsi": rsi,
                    "position_multiplier": position_multiplier,
                    "risk_amount": risk_amount,
                    "entry_date": df.index[i],
                }
                in_trade = True

        equity_curve.append(balance)

        # Track drawdown
        if balance > max_balance:
            max_balance = balance
        dd = (max_balance - balance) / max_balance * 100
        if dd > max_drawdown:
            max_drawdown = dd

    # Close any open trade at last price
    if in_trade and current_trade:
        last_close = df.iloc[-1]["Close"]
        if current_trade["direction"] == "BUY":
            pnl = last_close - current_trade["entry"]
        else:
            pnl = current_trade["entry"] - last_close
        pnl_dollar = pnl * current_trade["position_multiplier"]
        balance += pnl_dollar
        current_trade["exit"] = last_close
        current_trade["exit_reason"] = "End of Data"
        current_trade["pnl"] = round(pnl_dollar, 2)
        current_trade["exit_date"] = df.index[-1]
        trades.append(current_trade)

    # Calculate statistics
    if not trades:
        return {
            "ticker": ticker,
            "name": get_display_name(ticker),
            "total_trades": 0,
            "message": "No trades generated. Strategy may need different parameters.",
        }

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    total_profit = sum(t["pnl"] for t in wins)
    total_loss = abs(sum(t["pnl"] for t in losses))

    win_rate = len(wins) / len(trades) * 100 if trades else 0
    profit_factor = total_profit / total_loss if total_loss > 0 else float("inf")
    avg_win = total_profit / len(wins) if wins else 0
    avg_loss = total_loss / len(losses) if losses else 0
    expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss)

    net_pnl = balance - initial_balance
    net_return = (net_pnl / initial_balance) * 100

    # Calculate Sharpe-like ratio
    trade_returns = [t["pnl"] / initial_balance for t in trades]
    if len(trade_returns) > 1:
        avg_return = np.mean(trade_returns)
        std_return = np.std(trade_returns)
        sharpe = (avg_return / std_return) * np.sqrt(52) if std_return > 0 else 0  # Annualized
    else:
        sharpe = 0

    data_start = df.index[0].strftime("%Y-%m-%d") if hasattr(df.index[0], 'strftime') else str(df.index[0])
    data_end = df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], 'strftime') else str(df.index[-1])

    return {
        "ticker": ticker,
        "name": get_display_name(ticker),
        "period": f"{data_start} to {data_end}",
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "sharpe_ratio": round(sharpe, 2),
        "net_pnl": round(net_pnl, 2),
        "net_return_pct": round(net_return, 2),
        "total_profit": round(total_profit, 2),
        "total_loss": round(total_loss, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "initial_balance": initial_balance,
        "final_balance": round(balance, 2),
        "equity_curve": equity_curve,
        "trades": trades,
    }


def print_results(results):
    """Pretty print backtest results."""
    if results is None:
        print("No results to display.")
        return

    if results["total_trades"] == 0:
        print(f"\n{results['name']}: {results['message']}")
        return

    print(f"\n{'=' * 55}")
    print(f"BACKTEST RESULTS: {results['name']}")
    print(f"Period: {results['period']}")
    print(f"{'=' * 55}")
    print(f"  Total Trades:    {results['total_trades']}")
    print(f"  Wins / Losses:   {results['wins']} / {results['losses']}")
    print(f"  Win Rate:        {results['win_rate']}%")
    print(f"  Profit Factor:   {results['profit_factor']}")
    print(f"  Sharpe Ratio:    {results['sharpe_ratio']}")
    print(f"  {'─' * 35}")
    print(f"  Initial Balance: ${results['initial_balance']:,.2f}")
    print(f"  Final Balance:   ${results['final_balance']:,.2f}")
    print(f"  Net P&L:         ${results['net_pnl']:,.2f} ({results['net_return_pct']}%)")
    print(f"  {'─' * 35}")
    print(f"  Avg Win:         ${results['avg_win']:,.2f}")
    print(f"  Avg Loss:        ${results['avg_loss']:,.2f}")
    print(f"  Expectancy:      ${results['expectancy']:,.2f} per trade")
    print(f"  Max Drawdown:    {results['max_drawdown_pct']}%")
    print(f"{'=' * 55}")

    # Win/Loss assessment
    if results['win_rate'] >= 50 and results['profit_factor'] >= 1.3:
        print("  VERDICT: Strategy shows POSITIVE edge")
    elif results['profit_factor'] >= 1.0:
        print("  VERDICT: Strategy is MARGINALLY profitable")
    else:
        print("  VERDICT: Strategy needs IMPROVEMENT")


if __name__ == "__main__":
    import yfinance as yf

    print("Running backtest on Gold (daily data, 1 year)...")
    gold = yf.download("GC=F", period="1y", interval="1d", progress=False, auto_adjust=True)
    if isinstance(gold.columns, pd.MultiIndex):
        gold.columns = gold.columns.get_level_values(0)
    gold.columns = [c.title() for c in gold.columns]

    results = backtest_strategy(gold, ticker="GC=F")
    print_results(results)

    print("\n\nRunning backtest on RELIANCE (daily data, 1 year)...")
    reliance = yf.download("RELIANCE.NS", period="1y", interval="1d", progress=False, auto_adjust=True)
    if isinstance(reliance.columns, pd.MultiIndex):
        reliance.columns = reliance.columns.get_level_values(0)
    reliance.columns = [c.title() for c in reliance.columns]

    results = backtest_strategy(reliance, ticker="RELIANCE.NS")
    print_results(results)
