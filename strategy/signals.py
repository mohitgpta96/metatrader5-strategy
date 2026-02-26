"""
Signal generation engine.
Applies the Triple Confirmation strategy to generate BUY/SELL signals.

Strategy Rules (Two types of signals):

Type 1 - EMA Crossover (original):
  BUY:  EMA20 crosses above EMA50 + RSI 40-70
  SELL: EMA20 crosses below EMA50 + RSI 30-60

Type 2 - Trend Pullback (for trending markets like Gold):
  BUY:  Trend is bullish (EMA20 > EMA50) + price pulled back near EMA20 + RSI 35-55
  SELL: Trend is bearish (EMA20 < EMA50) + price bounced up near EMA20 + RSI 45-65
"""
import sys
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD,
    RSI_BUY_MIN, RSI_BUY_MAX, RSI_SELL_MIN, RSI_SELL_MAX,
    ADX_MIN_THRESHOLD, VOLUME_MIN_RATIO, MIN_SIGNAL_SCORE,
)
from strategy.indicators import add_indicators, get_current_indicators
from strategy.position_sizing import calculate_trade_levels
from config.instruments import get_display_name, get_instrument_type


def check_signal(df, df_confirmation=None, ticker=""):
    """
    Check for a trading signal on a DataFrame with OHLCV data.
    Checks both EMA crossover and trend pullback signals.

    Args:
        df: Primary timeframe DataFrame (1H for commodities, 1D for stocks)
        df_confirmation: Higher timeframe DataFrame for trend filter
        ticker: Instrument ticker for position sizing

    Returns:
        dict with signal info, or None if no signal
    """
    df = add_indicators(df)
    if df is None or df.empty:
        return None

    current = get_current_indicators(df)
    if current is None:
        return None

    if current["ema_fast"] is None or current["rsi"] is None or current["atr"] is None:
        return None

    adx = current.get("adx")
    vol_ratio = current.get("vol_ratio", 1.0)

    # --- FILTER 1: ADX Trend Strength ---
    # Skip if ADX is available but too low (weak/choppy trend)
    if adx is not None and not pd.isna(adx) and adx < ADX_MIN_THRESHOLD:
        return None

    # Get confirmation trend (higher timeframe)
    confirmation_trend = 0
    if df_confirmation is not None:
        df_conf = add_indicators(df_confirmation)
        conf_indicators = get_current_indicators(df_conf)
        if conf_indicators:
            confirmation_trend = conf_indicators["trend"]
    else:
        confirmation_trend = current["trend"]

    direction = None
    signal_type = None

    # --- Signal Type 1: EMA Crossover ---
    if (
        current["ema_cross"] == 1
        and RSI_BUY_MIN <= current["rsi"] <= RSI_BUY_MAX
        and confirmation_trend >= 0
    ):
        direction = "BUY"
        signal_type = "EMA Crossover"

    elif (
        current["ema_cross"] == -1
        and RSI_SELL_MIN <= current["rsi"] <= RSI_SELL_MAX
        and confirmation_trend <= 0
    ):
        direction = "SELL"
        signal_type = "EMA Crossover"

    # --- Signal Type 2: Trend Pullback ---
    if direction is None and len(df) >= 3:
        close = current["close"]
        ema_fast = current["ema_fast"]
        ema_slow = current["ema_slow"]
        atr = current["atr"]
        rsi = current["rsi"]

        # How close is price to EMA20? (within 0.5x ATR = "touching")
        distance_to_ema20 = abs(close - ema_fast)
        is_near_ema20 = distance_to_ema20 <= (0.5 * atr)

        # Previous candles - was there a pullback?
        prev1 = df.iloc[-2]

        if current["trend"] == 1 and confirmation_trend >= 0:
            price_was_lower = prev1["Low"] <= ema_fast * 1.003
            bouncing_up = close > prev1["Close"]

            if (
                is_near_ema20
                and 35 <= rsi <= 55
                and price_was_lower
                and bouncing_up
            ):
                direction = "BUY"
                signal_type = "Pullback Buy"

        elif current["trend"] == -1 and confirmation_trend <= 0:
            price_was_higher = prev1["High"] >= ema_fast * 0.997
            bouncing_down = close < prev1["Close"]

            if (
                is_near_ema20
                and 45 <= rsi <= 65
                and price_was_higher
                and bouncing_down
            ):
                direction = "SELL"
                signal_type = "Pullback Sell"

    if direction is None:
        return None

    # --- SIGNAL SCORING (1-10) ---
    score = _calculate_signal_score(
        direction=direction,
        signal_type=signal_type,
        adx=adx,
        rsi=current["rsi"],
        vol_ratio=vol_ratio,
        confirmation_trend=confirmation_trend,
        current=current,
    )

    # --- FILTER 2: Minimum Score ---
    if score < MIN_SIGNAL_SCORE:
        return None

    trade = calculate_trade_levels(
        ticker=ticker,
        entry_price=current["close"],
        atr=current["atr"],
        direction=direction,
    )

    if trade is None:
        return None

    signal = {
        "ticker": ticker,
        "name": get_display_name(ticker),
        "type": get_instrument_type(ticker),
        "direction": direction,
        "signal_type": signal_type,
        "signal_score": score,
        "entry": trade["entry"],
        "stop_loss": trade["stop_loss"],
        "tp1": trade["tp1"],
        "tp2": trade["tp2"],
        "lot_size": trade["lot_size"],
        "atr": trade["atr"],
        "rsi": round(current["rsi"], 1),
        "adx": round(adx, 1) if adx and not pd.isna(adx) else None,
        "vol_ratio": round(vol_ratio, 2) if vol_ratio and not pd.isna(vol_ratio) else None,
        "ema_fast": round(current["ema_fast"], 2),
        "ema_slow": round(current["ema_slow"], 2),
        "trend": current["trend_label"],
        "confirmation_trend": confirmation_trend,
        "rr_tp1": trade["rr_tp1"],
        "rr_tp2": trade["rr_tp2"],
        "potential_loss": trade["potential_loss"],
        "potential_tp1": trade["potential_tp1"],
        "potential_tp2": trade["potential_tp2"],
        "sl_distance": trade["sl_distance"],
        "was_capped": trade["was_capped"],
    }

    return signal


def _calculate_signal_score(direction, signal_type, adx, rsi, vol_ratio, confirmation_trend, current):
    """
    Calculate signal quality score from 1-10.
    Higher score = higher confidence signal.

    Scoring breakdown:
      - ADX strength:           0-3 points
      - Volume confirmation:    0-2 points
      - RSI position:           0-2 points
      - Trend alignment:        0-2 points
      - Signal type bonus:      0-1 point
    Total max: 10
    """
    score = 0

    # --- ADX Strength (0-3 points) ---
    if adx is not None and not pd.isna(adx):
        if adx >= 40:
            score += 3    # Very strong trend
        elif adx >= 30:
            score += 2    # Strong trend
        elif adx >= 25:
            score += 1    # Moderate trend
        # Below 25 = 0 points (but already filtered out by ADX_MIN_THRESHOLD)

    # --- Volume Confirmation (0-2 points) ---
    if vol_ratio is not None and not pd.isna(vol_ratio):
        if vol_ratio >= 1.5:
            score += 2    # Strong volume (1.5x+ average)
        elif vol_ratio >= VOLUME_MIN_RATIO:
            score += 1    # Decent volume (1.0x+ average)
        # Below average volume = 0 points

    # --- RSI Position (0-2 points) ---
    # Best RSI for BUY: 45-60 (momentum but not overbought)
    # Best RSI for SELL: 40-55 (weakening but not oversold)
    if rsi is not None and not pd.isna(rsi):
        if direction == "BUY":
            if 45 <= rsi <= 60:
                score += 2    # Sweet spot
            elif 40 <= rsi <= 70:
                score += 1    # Acceptable
        elif direction == "SELL":
            if 40 <= rsi <= 55:
                score += 2    # Sweet spot
            elif 30 <= rsi <= 65:
                score += 1    # Acceptable

    # --- Trend Alignment (0-2 points) ---
    primary_trend = current.get("trend", 0)
    if direction == "BUY":
        if primary_trend == 1 and confirmation_trend == 1:
            score += 2    # Both timeframes bullish
        elif primary_trend == 1 or confirmation_trend >= 0:
            score += 1    # At least primary is aligned
    elif direction == "SELL":
        if primary_trend == -1 and confirmation_trend == -1:
            score += 2    # Both timeframes bearish
        elif primary_trend == -1 or confirmation_trend <= 0:
            score += 1    # At least primary is aligned

    # --- Signal Type Bonus (0-1 point) ---
    if signal_type == "EMA Crossover":
        score += 1    # Crossover is a stronger signal than pullback

    return min(10, score)


def check_trend_status(df, ticker=""):
    """
    Get current market status without requiring a signal.
    Used for daily digest.
    """
    df = add_indicators(df)
    if df is None or df.empty:
        return None

    current = get_current_indicators(df)
    if current is None:
        return None

    if current["ema_fast"] is None or current["rsi"] is None:
        return None

    if current["rsi"] > 70:
        condition = "OVERBOUGHT"
    elif current["rsi"] < 30:
        condition = "OVERSOLD"
    elif current["trend"] == 1 and current["rsi"] > 50:
        condition = "STRONG BULLISH"
    elif current["trend"] == 1:
        condition = "BULLISH"
    elif current["trend"] == -1 and current["rsi"] < 50:
        condition = "STRONG BEARISH"
    elif current["trend"] == -1:
        condition = "BEARISH"
    else:
        condition = "NEUTRAL"

    return {
        "ticker": ticker,
        "name": get_display_name(ticker),
        "type": get_instrument_type(ticker),
        "close": round(current["close"], 2),
        "ema_fast": round(current["ema_fast"], 2) if current["ema_fast"] else None,
        "ema_slow": round(current["ema_slow"], 2) if current["ema_slow"] else None,
        "rsi": round(current["rsi"], 1) if current["rsi"] else None,
        "atr": round(current["atr"], 2) if current["atr"] else None,
        "trend": current["trend_label"],
        "condition": condition,
    }


if __name__ == "__main__":
    import yfinance as yf

    print("Testing signal engine...")
    print("=" * 50)

    # Test with Gold
    print("\n--- Gold (GC=F) Signal Check ---")
    gold_1h = yf.download("GC=F", period="60d", interval="1h", progress=False, auto_adjust=True)
    if isinstance(gold_1h.columns, pd.MultiIndex):
        gold_1h.columns = gold_1h.columns.get_level_values(0)
    gold_1h.columns = [c.title() for c in gold_1h.columns]

    signal = check_signal(gold_1h, ticker="GC=F")
    if signal:
        print(f"  SIGNAL: {signal['direction']} ({signal['signal_type']})")
        print(f"  Entry: ${signal['entry']}")
        print(f"  SL: ${signal['stop_loss']}")
        print(f"  TP1: ${signal['tp1']}")
        print(f"  Lot: {signal['lot_size']}")
    else:
        print("  No active signal right now")

    status = check_trend_status(gold_1h, ticker="GC=F")
    if status:
        print(f"\n  Market Status:")
        print(f"  Price: ${status['close']} | Trend: {status['trend']} | RSI: {status['rsi']}")
        print(f"  Condition: {status['condition']}")
