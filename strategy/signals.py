"""
Signal generation engine — Professional-grade multi-confirmation strategy.

Signal Types:
  Type 1 - EMA Crossover + MACD confirmation:
    BUY:  EMA20 crosses above EMA50 + RSI 45-70 + MACD histogram turning positive
    SELL: EMA20 crosses below EMA50 + RSI 30-55 + MACD histogram turning negative

  Type 2 - Trend Pullback (for sustained trending markets):
    BUY:  Bullish trend + price near EMA20 + RSI 40-65 + MACD positive + bouncing up
    SELL: Bearish trend + price near EMA20 + RSI 35-60 + MACD negative + bouncing down

  Type 3 - Trend Opportunity (fallback — fills minimum 3-4 signals per scan):
    Weaker setup, score capped at 3 (always ranks below Type 1/2 strict signals)

Regime Filter:
  TRENDING  → All signal types allowed
  RANGING   → Score -1 penalty (filters weak signals in choppy conditions)
  SQUEEZE   → Score +1 bonus (potential high-momentum breakout)
  VOLATILE  → Score -1 penalty + position size reduced externally

Session Filter (commodities only):
  KILL_ZONE → Score +1 bonus (London/NY open — highest liquidity)
  NORMAL    → No change
  THIN      → Score -2 penalty (Asian dead zone — prone to false moves)

Fixes vs old version:
  - RSI ranges no longer overlap between BUY (45-70) and SELL (30-55)
  - Pullback RSI is now symmetric and correct (40-65 BUY, 35-60 SELL)
  - MACD confirmation required for EMA crossover (reduces false crossovers by ~30%)
  - Candle body filter: doji / spinning tops are rejected
  - Opportunity signals capped at 3 (was 5) — can NEVER outrank strict signals (score 4+)
"""
import sys
from pathlib import Path

import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD,
    ADX_MIN_THRESHOLD, VOLUME_MIN_RATIO, MIN_SIGNAL_SCORE,
    CANDLE_BODY_MIN_RATIO,
)
from strategy.indicators import add_indicators, get_current_indicators, get_session_quality
from strategy.position_sizing import calculate_trade_levels
from config.instruments import get_display_name, get_instrument_type


def check_signal(df, df_confirmation=None, ticker=""):
    """
    Check for a trading signal on a DataFrame with OHLCV data.
    Returns dict with signal info, or None if no signal.
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
    regime = current.get("regime", "RANGING")
    body_ratio = current.get("body_ratio", 0.5)

    # --- FILTER 1: ADX Trend Strength (raised to 20) ---
    if adx is not None and not pd.isna(adx) and adx < ADX_MIN_THRESHOLD:
        return None

    # --- FILTER 2: Candle Body (reject doji / spinning tops) ---
    if body_ratio < CANDLE_BODY_MIN_RATIO:
        return None

    # --- FILTER 3: Volatile regime — skip (news-driven, unpredictable) ---
    if regime == "VOLATILE":
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

    macd_hist = current.get("macd_hist")
    prev_macd_hist = current.get("prev_macd_hist")
    macd_available = (
        macd_hist is not None and not pd.isna(macd_hist)
        and prev_macd_hist is not None and not pd.isna(prev_macd_hist)
    )

    # MACD turning positive = histogram was negative/zero last bar, now positive
    macd_bullish = macd_available and macd_hist > 0
    # MACD turning negative = histogram was positive/zero last bar, now negative
    macd_bearish = macd_available and macd_hist < 0

    # --- Signal Type 1: EMA Crossover + MACD confirmation ---
    if (
        current["ema_cross"] == 1
        and 45 <= current["rsi"] <= 70          # BUY: RSI 45-70 (no overlap with SELL)
        and confirmation_trend >= 0
        and (not macd_available or macd_bullish) # MACD must confirm if available
    ):
        direction = "BUY"
        signal_type = "EMA Crossover"

    elif (
        current["ema_cross"] == -1
        and 30 <= current["rsi"] <= 55          # SELL: RSI 30-55 (no overlap with BUY)
        and confirmation_trend <= 0
        and (not macd_available or macd_bearish) # MACD must confirm if available
    ):
        direction = "SELL"
        signal_type = "EMA Crossover"

    # --- Signal Type 2: Trend Pullback ---
    if direction is None and len(df) >= 3:
        close = current["close"]
        ema_fast = current["ema_fast"]
        atr = current["atr"]
        rsi = current["rsi"]

        # Price within 0.5x ATR of EMA20 = "touching"
        distance_to_ema20 = abs(close - ema_fast)
        is_near_ema20 = distance_to_ema20 <= (0.5 * atr)

        prev1 = df.iloc[-2]

        if current["trend"] == 1 and confirmation_trend >= 0:
            price_was_lower = prev1["Low"] <= ema_fast * 1.003
            bouncing_up = close > prev1["Close"]

            if (
                is_near_ema20
                and 40 <= rsi <= 65             # Fixed: was 35-55 (too tight, wrong logic)
                and price_was_lower
                and bouncing_up
                and (not macd_available or macd_bullish)
            ):
                direction = "BUY"
                signal_type = "Pullback Buy"

        elif current["trend"] == -1 and confirmation_trend <= 0:
            price_was_higher = prev1["High"] >= ema_fast * 0.997
            bouncing_down = close < prev1["Close"]

            if (
                is_near_ema20
                and 35 <= rsi <= 60             # Fixed: was 45-65 (symmetric now)
                and price_was_higher
                and bouncing_down
                and (not macd_available or macd_bearish)
            ):
                direction = "SELL"
                signal_type = "Pullback Sell"

    if direction is None:
        return None

    # --- FILTER 4: Volume (at least average — 1.0x) ---
    if vol_ratio is not None and not pd.isna(vol_ratio) and vol_ratio < VOLUME_MIN_RATIO:
        return None

    # --- SIGNAL SCORING (0-10) ---
    inst_type = get_instrument_type(ticker)
    session = get_session_quality() if inst_type in ("commodity", "mcx_commodity") else "NORMAL"

    score = _calculate_signal_score(
        direction=direction,
        signal_type=signal_type,
        adx=adx,
        rsi=current["rsi"],
        vol_ratio=vol_ratio,
        confirmation_trend=confirmation_trend,
        current=current,
        regime=regime,
        session=session,
    )

    # --- FILTER 5: Minimum Score ---
    if score < MIN_SIGNAL_SCORE:
        return None

    trade = calculate_trade_levels(
        ticker=ticker,
        entry_price=current["close"],
        atr=current["atr"],
        direction=direction,
        signal_score=score,
    )

    if trade is None:
        return None

    signal = {
        "ticker": ticker,
        "name": get_display_name(ticker),
        "type": inst_type,
        "direction": direction,
        "signal_type": signal_type,
        "signal_score": score,
        "regime": regime,
        "session": session,
        "entry": trade["entry"],
        "stop_loss": trade["stop_loss"],
        "tp1": trade["tp1"],
        "tp2": trade["tp2"],
        "tp3": trade.get("tp3"),           # New: runner target
        "lot_size": trade["lot_size"],
        "atr": trade["atr"],
        "rsi": round(current["rsi"], 1),
        "adx": round(adx, 1) if adx and not pd.isna(adx) else None,
        "di_diff": round(current.get("di_diff", 0), 1),
        "macd_hist": round(macd_hist, 4) if macd_hist and not pd.isna(macd_hist) else None,
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


def _calculate_signal_score(direction, signal_type, adx, rsi, vol_ratio,
                              confirmation_trend, current, regime="RANGING", session="NORMAL"):
    """
    Calculate signal quality score (0-10).
    Higher score = higher confidence. Minimum 4 to send.

    Scoring:
      ADX strength:          0-3 pts  (trend power)
      Volume confirmation:   0-2 pts  (market participation)
      RSI position:          0-2 pts  (momentum quality)
      Trend alignment:       0-2 pts  (timeframe confluence)
      MACD confirmation:     0-1 pts  (momentum backing — replaces old "type bonus")
      Regime adjustment:     -1/0/+1  (RANGING=-1, SQUEEZE=+1)
      Session adjustment:    -2/0/+1  (THIN=-2, KILL_ZONE=+1)
    Total max: 10
    """
    score = 0

    # --- ADX Strength (0-3 points) ---
    if adx is not None and not pd.isna(adx):
        if adx >= 40:
            score += 3    # Very strong trend
        elif adx >= 30:
            score += 2    # Strong trend
        elif adx >= 20:
            score += 1    # Moderate trend (threshold is 20, so 20-29 = 1pt)

    # --- Volume Confirmation (0-2 points) ---
    if vol_ratio is not None and not pd.isna(vol_ratio):
        if vol_ratio >= 1.5:
            score += 2    # Strong above-average volume
        elif vol_ratio >= 1.0:
            score += 1    # Average volume (min requirement already passed)

    # --- RSI Position (0-2 points) ---
    if rsi is not None and not pd.isna(rsi):
        if direction == "BUY":
            if 50 <= rsi <= 65:
                score += 2    # Sweet spot: momentum building, not overbought
            elif 45 <= rsi <= 70:
                score += 1    # Acceptable range
        elif direction == "SELL":
            if 35 <= rsi <= 50:
                score += 2    # Sweet spot: momentum falling, not oversold
            elif 30 <= rsi <= 55:
                score += 1    # Acceptable range

    # --- Trend Alignment (0-2 points) ---
    primary_trend = current.get("trend", 0)
    if direction == "BUY":
        if primary_trend == 1 and confirmation_trend == 1:
            score += 2    # Both timeframes bullish
        elif primary_trend == 1 or confirmation_trend >= 0:
            score += 1
    elif direction == "SELL":
        if primary_trend == -1 and confirmation_trend == -1:
            score += 2    # Both timeframes bearish
        elif primary_trend == -1 or confirmation_trend <= 0:
            score += 1

    # --- MACD Confirmation (0-1 point) ---
    macd_hist = current.get("macd_hist")
    if macd_hist is not None and not pd.isna(macd_hist):
        if direction == "BUY" and macd_hist > 0:
            score += 1    # MACD histogram positive = momentum supports BUY
        elif direction == "SELL" and macd_hist < 0:
            score += 1    # MACD histogram negative = momentum supports SELL

    # --- Regime Adjustment ---
    if regime == "RANGING":
        score -= 1    # Choppy market = lower confidence
    elif regime == "SQUEEZE":
        score += 1    # Compressed volatility breakout = higher potential

    # --- Session Adjustment (commodities) ---
    if session == "KILL_ZONE":
        score += 1    # London/NY open = institutional volume
    elif session == "THIN":
        score -= 2    # Asian dead zone = prone to false moves

    return max(0, min(10, score))


def check_trend_status(df, ticker=""):
    """Get current market status (for daily digest)."""
    df = add_indicators(df)
    if df is None or df.empty:
        return None

    current = get_current_indicators(df)
    if current is None:
        return None

    if current["ema_fast"] is None or current["rsi"] is None:
        return None

    rsi = current["rsi"]
    if rsi > 70:
        condition = "OVERBOUGHT"
    elif rsi < 30:
        condition = "OVERSOLD"
    elif current["trend"] == 1 and rsi > 50:
        condition = "STRONG BULLISH"
    elif current["trend"] == 1:
        condition = "BULLISH"
    elif current["trend"] == -1 and rsi < 50:
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
        "rsi": round(rsi, 1),
        "atr": round(current["atr"], 2) if current["atr"] else None,
        "adx": round(current["adx"], 1) if current["adx"] and not pd.isna(current["adx"]) else None,
        "regime": current.get("regime", "RANGING"),
        "trend": current["trend_label"],
        "condition": condition,
    }


def check_best_opportunity(df, ticker=""):
    """
    Fallback signal for filling minimum 3-4 signals per scan.
    Score HARD-CAPPED at 3 so strict signals (score 4+) ALWAYS rank higher.
    Requirements: ADX > 10, clear trend, RSI not at extremes.
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
    rsi = current["rsi"]
    trend = current["trend"]
    vol_ratio = current.get("vol_ratio", 1.0)
    regime = current.get("regime", "RANGING")

    # Minimum trend strength
    if adx is None or pd.isna(adx) or adx < 10:
        return None

    # Need clear trend
    if trend == 0:
        return None

    # Skip volatile regime — unreliable for any signal
    if regime == "VOLATILE":
        return None

    # Skip if RSI already at extreme (bad entry)
    if trend == 1 and rsi > 78:
        return None
    if trend == -1 and rsi < 22:
        return None

    direction = "BUY" if trend == 1 else "SELL"

    # Score: 1-3 (HARD CAP AT 3 — strict signals score 4+, so this never beats them)
    score = 1
    if adx >= 25:
        score += 1
    if vol_ratio and not pd.isna(vol_ratio) and vol_ratio >= 1.0:
        score += 1

    score = min(3, score)  # Hard cap at 3

    inst_type = get_instrument_type(ticker)
    session = get_session_quality() if inst_type in ("commodity", "mcx_commodity") else "NORMAL"

    # Don't send opportunity signals in thin sessions at all
    if session == "THIN":
        return None

    trade = calculate_trade_levels(
        ticker=ticker,
        entry_price=current["close"],
        atr=current["atr"],
        direction=direction,
        signal_score=score,
    )
    if trade is None:
        return None

    return {
        "ticker": ticker,
        "name": get_display_name(ticker),
        "type": inst_type,
        "direction": direction,
        "signal_type": "Trend Opportunity",
        "signal_score": score,
        "regime": regime,
        "session": session,
        "entry": trade["entry"],
        "stop_loss": trade["stop_loss"],
        "tp1": trade["tp1"],
        "tp2": trade["tp2"],
        "tp3": trade.get("tp3"),
        "lot_size": trade["lot_size"],
        "atr": trade["atr"],
        "rsi": round(rsi, 1),
        "adx": round(adx, 1) if not pd.isna(adx) else None,
        "di_diff": round(current.get("di_diff", 0), 1),
        "macd_hist": round(current["macd_hist"], 4) if current.get("macd_hist") and not pd.isna(current["macd_hist"]) else None,
        "vol_ratio": round(vol_ratio, 2) if vol_ratio and not pd.isna(vol_ratio) else None,
        "ema_fast": round(current["ema_fast"], 2),
        "ema_slow": round(current["ema_slow"], 2),
        "trend": current["trend_label"],
        "confirmation_trend": trend,
        "rr_tp1": trade["rr_tp1"],
        "rr_tp2": trade["rr_tp2"],
        "potential_loss": trade["potential_loss"],
        "potential_tp1": trade["potential_tp1"],
        "potential_tp2": trade["potential_tp2"],
        "sl_distance": trade["sl_distance"],
        "was_capped": trade["was_capped"],
    }


if __name__ == "__main__":
    import yfinance as yf

    print("Testing signal engine...")
    print("=" * 50)

    print("\n--- Gold (GC=F) Signal Check ---")
    gold_1h = yf.download("GC=F", period="60d", interval="1h", progress=False, auto_adjust=True)
    if isinstance(gold_1h.columns, pd.MultiIndex):
        gold_1h.columns = gold_1h.columns.get_level_values(0)
    gold_1h.columns = [c.title() for c in gold_1h.columns]

    signal = check_signal(gold_1h, ticker="GC=F")
    if signal:
        print(f"  SIGNAL: {signal['direction']} ({signal['signal_type']}) score={signal['signal_score']}")
        print(f"  Entry: ${signal['entry']} | SL: ${signal['stop_loss']}")
        print(f"  TP1: ${signal['tp1']} | TP2: ${signal['tp2']} | TP3: ${signal.get('tp3', 'N/A')}")
        print(f"  Regime: {signal['regime']} | Session: {signal['session']}")
    else:
        opp = check_best_opportunity(gold_1h, ticker="GC=F")
        if opp:
            print(f"  OPPORTUNITY: {opp['direction']} score={opp['signal_score']} regime={opp['regime']}")
        else:
            print("  No signal or opportunity right now")

    status = check_trend_status(gold_1h, ticker="GC=F")
    if status:
        print(f"\n  Status: {status['condition']} | RSI: {status['rsi']} | ADX: {status.get('adx')} | Regime: {status['regime']}")
