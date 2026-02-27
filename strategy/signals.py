"""
Signal generation engine — Professional-grade multi-confirmation strategy.

Signal Types (in priority order):
  Type 1 - EMA Crossover + MACD confirmation:
    BUY:  EMA20 crosses above EMA50 + RSI 45-70 + MACD hist positive
    SELL: EMA20 crosses below EMA50 + RSI 30-55 + MACD hist negative

  Type 2 - BOS/CHoCH (Break of Structure / Change of Character):
    BOS  BUY:  Uptrend + close breaks above prev swing high   → trend continuation
    BOS  SELL: Downtrend + close breaks below prev swing low  → trend continuation
    CHoCH BUY: Downtrend + close breaks above swing high      → early reversal
    CHoCH SELL:Uptrend   + close breaks below swing low       → early reversal

  Type 3 - SuperTrend Flip:
    BUY:  SuperTrend direction just flipped to +1 (bullish)
    SELL: SuperTrend direction just flipped to -1 (bearish)

  Type 4 - Trend Pullback (price near EMA20, bouncing in trend direction):
    BUY:  Bullish trend + near EMA20 + RSI 40-65 + MACD pos + bouncing up
    SELL: Bearish trend + near EMA20 + RSI 35-60 + MACD neg + bouncing down

  Type 5 - FVG Retracement (price enters unfilled Fair Value Gap zone):
    BUY:  Price in bullish FVG zone + bullish trend + RSI < 65
    SELL: Price in bearish FVG zone + bearish trend + RSI > 35

Signal Score (0-10, capped):
  ADX strength        0-3 pts   (trend power)
  Volume              0-2 pts   (market participation)
  RSI position        0-2 pts   (momentum quality)
  Trend alignment     0-2 pts   (timeframe confluence)
  MACD confirmation   0-1 pts   (momentum backing)
  SuperTrend align    0-1 pts   (directional filter)
  StochRSI position   0-1 pts   (overbought/oversold sensitivity)
  BOS confirmation    0-1 pts   (structure break confirmation)
  FVG zone            0-1 pts   (institutional imbalance entry)
  Divergence          0-2 pts   (RSI/MACD divergence = momentum building)
  Regime              -1/0/+1   (RANGING=-1, SQUEEZE=+1)
  Session             -2/0/+1   (THIN=-2, KILL_ZONE=+1)
  Maximum = 10 (capped)

Fallback (Type 3 opportunity) score HARD-CAPPED at 3.
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
from strategy.indicators import (
    add_indicators, get_current_indicators, get_session_quality,
    detect_fair_value_gaps, detect_order_blocks, detect_divergence,
)
from strategy.position_sizing import calculate_trade_levels
from config.instruments import get_display_name, get_instrument_type


def check_signal(df, df_confirmation=None, ticker=""):
    """
    Check for a trading signal on a DataFrame with OHLCV data.
    Returns dict with signal info, or None if no signal.

    Signal types checked in priority order:
      1. EMA Crossover + MACD
      2. BOS / CHoCH (market structure break)
      3. SuperTrend Flip
      4. Trend Pullback
      5. FVG Retracement
    """
    df = add_indicators(df)
    if df is None or df.empty:
        return None

    current = get_current_indicators(df)
    if current is None:
        return None

    if current["ema_fast"] is None or current["rsi"] is None or current["atr"] is None:
        return None

    adx       = current.get("adx")
    vol_ratio = current.get("vol_ratio", 1.0)
    regime    = current.get("regime", "RANGING")
    body_ratio= current.get("body_ratio", 0.5)

    # ── HARD FILTERS (apply to ALL signal types) ──────────────────────────────
    # Filter 1: ADX trend strength
    if adx is not None and not pd.isna(adx) and adx < ADX_MIN_THRESHOLD:
        return None

    # Filter 2: Candle body (reject doji / spinning tops)
    if body_ratio < CANDLE_BODY_MIN_RATIO:
        return None

    # Filter 3: VOLATILE regime — news-driven, skip entirely
    if regime == "VOLATILE":
        return None

    # ── Higher timeframe confirmation trend ───────────────────────────────────
    confirmation_trend = 0
    if df_confirmation is not None:
        df_conf     = add_indicators(df_confirmation)
        conf_indics = get_current_indicators(df_conf)
        if conf_indics:
            confirmation_trend = conf_indics["trend"]
    else:
        confirmation_trend = current["trend"]

    # ── Standalone detectors (called once, used in all types + scoring) ───────
    fvg_zones  = detect_fair_value_gaps(df)
    divergence = detect_divergence(df)

    # ── MACD state ────────────────────────────────────────────────────────────
    macd_hist      = current.get("macd_hist")
    prev_macd_hist = current.get("prev_macd_hist")
    macd_available = (
        macd_hist is not None and not pd.isna(macd_hist) and
        prev_macd_hist is not None and not pd.isna(prev_macd_hist)
    )
    macd_bullish = macd_available and macd_hist > 0
    macd_bearish = macd_available and macd_hist < 0

    # ── SuperTrend state ──────────────────────────────────────────────────────
    st_dir      = current.get("supertrend_dir", 0)
    prev_st_dir = current.get("prev_supertrend_dir", 0)
    st_flipped  = (st_dir != 0 and prev_st_dir != 0 and st_dir != prev_st_dir)

    direction   = None
    signal_type = None

    # ════════════════════════════════════════════════════════════════════════
    # TYPE 1: EMA Crossover + MACD confirmation
    # ════════════════════════════════════════════════════════════════════════
    if (current["ema_cross"] == 1
            and 45 <= current["rsi"] <= 70
            and confirmation_trend >= 0
            and (not macd_available or macd_bullish)):
        direction   = "BUY"
        signal_type = "EMA Crossover"

    elif (current["ema_cross"] == -1
            and 30 <= current["rsi"] <= 55
            and confirmation_trend <= 0
            and (not macd_available or macd_bearish)):
        direction   = "SELL"
        signal_type = "EMA Crossover"

    # ════════════════════════════════════════════════════════════════════════
    # TYPE 2: BOS / CHoCH (market structure break)
    # ════════════════════════════════════════════════════════════════════════
    if direction is None:
        bos   = current.get("bos", 0)
        choch = current.get("choch", 0)
        rsi   = current["rsi"]

        # BOS continuation (trade with trend)
        if bos == 1 and confirmation_trend >= 0 and 35 <= rsi <= 70:
            direction   = "BUY"
            signal_type = "BOS Bullish"
        elif bos == -1 and confirmation_trend <= 0 and 30 <= rsi <= 65:
            direction   = "SELL"
            signal_type = "BOS Bearish"

        # CHoCH reversal (counter-trend, needs strong confirmation)
        elif choch == 1 and 30 <= rsi <= 65:
            direction   = "BUY"
            signal_type = "CHoCH Bullish"
        elif choch == -1 and 35 <= rsi <= 70:
            direction   = "SELL"
            signal_type = "CHoCH Bearish"

    # ════════════════════════════════════════════════════════════════════════
    # TYPE 3: SuperTrend Flip
    # ════════════════════════════════════════════════════════════════════════
    if direction is None and st_flipped:
        rsi = current["rsi"]
        if st_dir == 1 and confirmation_trend >= 0 and 35 <= rsi <= 72:
            direction   = "BUY"
            signal_type = "SuperTrend Flip"
        elif st_dir == -1 and confirmation_trend <= 0 and 28 <= rsi <= 65:
            direction   = "SELL"
            signal_type = "SuperTrend Flip"

    # ════════════════════════════════════════════════════════════════════════
    # TYPE 4: Trend Pullback (most common type)
    # ════════════════════════════════════════════════════════════════════════
    if direction is None and len(df) >= 3:
        close    = current["close"]
        ema_fast = current["ema_fast"]
        atr      = current["atr"]
        rsi      = current["rsi"]

        distance_to_ema20 = abs(close - ema_fast)
        is_near_ema20     = distance_to_ema20 <= (0.5 * atr)
        prev1             = df.iloc[-2]

        if current["trend"] == 1 and confirmation_trend >= 0:
            price_was_lower = prev1["Low"] <= ema_fast * 1.003
            bouncing_up     = close > prev1["Close"]
            if (is_near_ema20 and 40 <= rsi <= 65
                    and price_was_lower and bouncing_up
                    and (not macd_available or macd_bullish)):
                direction   = "BUY"
                signal_type = "Pullback Buy"

        elif current["trend"] == -1 and confirmation_trend <= 0:
            price_was_higher = prev1["High"] >= ema_fast * 0.997
            bouncing_down    = close < prev1["Close"]
            if (is_near_ema20 and 35 <= rsi <= 60
                    and price_was_higher and bouncing_down
                    and (not macd_available or macd_bearish)):
                direction   = "SELL"
                signal_type = "Pullback Sell"

    # ════════════════════════════════════════════════════════════════════════
    # TYPE 5: FVG Retracement
    # ════════════════════════════════════════════════════════════════════════
    if direction is None:
        rsi   = current["rsi"]
        trend = current["trend"]

        bull_in_zone = any(f["in_zone"] for f in fvg_zones.get("bull_fvg", []))
        bear_in_zone = any(f["in_zone"] for f in fvg_zones.get("bear_fvg", []))

        if (bull_in_zone and trend == 1 and confirmation_trend >= 0
                and 30 <= rsi <= 65
                and (not macd_available or macd_bullish)):
            direction   = "BUY"
            signal_type = "FVG Buy"

        elif (bear_in_zone and trend == -1 and confirmation_trend <= 0
                and 35 <= rsi <= 70
                and (not macd_available or macd_bearish)):
            direction   = "SELL"
            signal_type = "FVG Sell"

    if direction is None:
        return None

    # ── Volume filter ─────────────────────────────────────────────────────────
    if vol_ratio is not None and not pd.isna(vol_ratio) and vol_ratio < VOLUME_MIN_RATIO:
        return None

    # ── Score ─────────────────────────────────────────────────────────────────
    inst_type = get_instrument_type(ticker)
    session   = get_session_quality() if inst_type in ("commodity", "mcx_commodity") else "NORMAL"

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
        fvg_zones=fvg_zones,
        divergence=divergence,
    )

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
        "ticker":       ticker,
        "name":         get_display_name(ticker),
        "type":         inst_type,
        "direction":    direction,
        "signal_type":  signal_type,
        "signal_score": score,
        "regime":       regime,
        "session":      session,
        "entry":        trade["entry"],
        "stop_loss":    trade["stop_loss"],
        "tp1":          trade["tp1"],
        "tp2":          trade["tp2"],
        "tp3":          trade.get("tp3"),
        "lot_size":     trade["lot_size"],
        "atr":          trade["atr"],
        "rsi":          round(current["rsi"], 1),
        "adx":          round(adx, 1) if adx and not pd.isna(adx) else None,
        "di_diff":      round(current.get("di_diff", 0), 1),
        "macd_hist":    round(macd_hist, 4) if macd_hist and not pd.isna(macd_hist) else None,
        "vol_ratio":    round(vol_ratio, 2) if vol_ratio and not pd.isna(vol_ratio) else None,
        "ema_fast":     round(current["ema_fast"], 2),
        "ema_slow":     round(current["ema_slow"], 2),
        "trend":        current["trend_label"],
        "confirmation_trend": confirmation_trend,
        "rr_tp1":       trade["rr_tp1"],
        "rr_tp2":       trade["rr_tp2"],
        "potential_loss":  trade["potential_loss"],
        "potential_tp1":   trade["potential_tp1"],
        "potential_tp2":   trade["potential_tp2"],
        "sl_distance":     trade["sl_distance"],
        "was_capped":      trade["was_capped"],
        # Extra context for transparency
        "supertrend_dir":  current.get("supertrend_dir", 0),
        "bos":             current.get("bos", 0),
        "choch":           current.get("choch", 0),
        "divergence":      divergence,
    }
    return signal


def _calculate_signal_score(direction, signal_type, adx, rsi, vol_ratio,
                             confirmation_trend, current, regime="RANGING",
                             session="NORMAL", fvg_zones=None, divergence=None):
    """
    Calculate signal quality score (0-10, capped).

    Component breakdown:
      ADX strength:        0-3   (20-29=1, 30-39=2, 40+=3)
      Volume:              0-2   (1.0x=1, 1.5x+=2)
      RSI position:        0-2   (sweet spot=2, acceptable=1)
      Trend alignment:     0-2   (both TF match=2, one TF=1)
      MACD confirmation:   0-1
      SuperTrend alignment:0-1
      StochRSI position:   0-1
      BOS confirmation:    0-1
      FVG zone:            0-1
      Divergence:          0-2
      Regime:              -1 (RANGING) / 0 / +1 (SQUEEZE)
      Session:             -2 (THIN) / 0 / +1 (KILL_ZONE)
    """
    score = 0

    # ── ADX (0-3) ──
    if adx is not None and not pd.isna(adx):
        if adx >= 40:   score += 3
        elif adx >= 30: score += 2
        elif adx >= 20: score += 1

    # ── Volume (0-2) ──
    if vol_ratio is not None and not pd.isna(vol_ratio):
        if vol_ratio >= 1.5:   score += 2
        elif vol_ratio >= 1.0: score += 1

    # ── RSI position (0-2) ──
    if rsi is not None and not pd.isna(rsi):
        if direction == "BUY":
            if 50 <= rsi <= 65:  score += 2   # Sweet spot
            elif 45 <= rsi <= 70: score += 1
        elif direction == "SELL":
            if 35 <= rsi <= 50:  score += 2   # Sweet spot
            elif 30 <= rsi <= 55: score += 1

    # ── Trend alignment (0-2) ──
    primary_trend = current.get("trend", 0)
    if direction == "BUY":
        if primary_trend == 1 and confirmation_trend == 1:   score += 2
        elif primary_trend == 1 or confirmation_trend >= 0:  score += 1
    elif direction == "SELL":
        if primary_trend == -1 and confirmation_trend == -1: score += 2
        elif primary_trend == -1 or confirmation_trend <= 0: score += 1

    # ── MACD confirmation (0-1) ──
    macd_hist = current.get("macd_hist")
    if macd_hist is not None and not pd.isna(macd_hist):
        if direction == "BUY" and macd_hist > 0:   score += 1
        elif direction == "SELL" and macd_hist < 0: score += 1

    # ── SuperTrend alignment (0-1) ── NEW
    st_dir = current.get("supertrend_dir", 0)
    if direction == "BUY" and st_dir == 1:    score += 1
    elif direction == "SELL" and st_dir == -1: score += 1

    # ── StochRSI position (0-1) ── NEW
    srsi_k = current.get("stochrsi_k")
    srsi_d = current.get("stochrsi_d")
    if srsi_k is not None and not pd.isna(srsi_k) and srsi_d is not None and not pd.isna(srsi_d):
        if direction == "BUY" and srsi_k > srsi_d:     score += 1   # K > D = momentum rising
        elif direction == "SELL" and srsi_k < srsi_d:  score += 1   # K < D = momentum falling

    # ── BOS confirmation (0-1) ── NEW
    bos = current.get("bos", 0)
    if direction == "BUY" and bos == 1:    score += 1
    elif direction == "SELL" and bos == -1: score += 1

    # ── FVG zone (0-1) ── NEW
    if fvg_zones:
        if direction == "BUY" and any(f["in_zone"] for f in fvg_zones.get("bull_fvg", [])):
            score += 1
        elif direction == "SELL" and any(f["in_zone"] for f in fvg_zones.get("bear_fvg", [])):
            score += 1

    # ── Divergence (0-2) ── NEW  — strong momentum reversal signal
    if divergence:
        if direction == "BUY" and (divergence.get("bull_rsi") or divergence.get("bull_macd")):
            score += 2
        elif direction == "SELL" and (divergence.get("bear_rsi") or divergence.get("bear_macd")):
            score += 2

    # ── Regime adjustment ──
    if regime == "RANGING":  score -= 1
    elif regime == "SQUEEZE": score += 1

    # ── Session adjustment (commodities only) ──
    if session == "KILL_ZONE": score += 1
    elif session == "THIN":    score -= 2

    return max(0, min(10, score))


def check_trend_status(df, ticker=""):
    """Get current market status (for daily digest / weekly report)."""
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
        "ticker":    ticker,
        "name":      get_display_name(ticker),
        "type":      get_instrument_type(ticker),
        "close":     round(current["close"], 2),
        "ema_fast":  round(current["ema_fast"], 2) if current["ema_fast"] else None,
        "ema_slow":  round(current["ema_slow"], 2) if current["ema_slow"] else None,
        "rsi":       round(rsi, 1),
        "atr":       round(current["atr"], 2) if current["atr"] else None,
        "adx":       round(current["adx"], 1) if current["adx"] and not pd.isna(current["adx"]) else None,
        "regime":    current.get("regime", "RANGING"),
        "trend":     current["trend_label"],
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

    adx       = current.get("adx")
    rsi       = current["rsi"]
    trend     = current["trend"]
    vol_ratio = current.get("vol_ratio", 1.0)
    regime    = current.get("regime", "RANGING")

    if adx is None or pd.isna(adx) or adx < 10:
        return None
    if trend == 0:
        return None
    if regime == "VOLATILE":
        return None
    if trend == 1  and rsi > 78: return None
    if trend == -1 and rsi < 22: return None

    direction = "BUY" if trend == 1 else "SELL"

    # Score: 1-3 (hard cap — strict signals score 4+, so this never beats them)
    score = 1
    if adx >= 25:
        score += 1
    if vol_ratio and not pd.isna(vol_ratio) and vol_ratio >= 1.0:
        score += 1
    score = min(3, score)

    inst_type = get_instrument_type(ticker)
    session   = get_session_quality() if inst_type in ("commodity", "mcx_commodity") else "NORMAL"

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
        "ticker":       ticker,
        "name":         get_display_name(ticker),
        "type":         inst_type,
        "direction":    direction,
        "signal_type":  "Trend Opportunity",
        "signal_score": score,
        "regime":       regime,
        "session":      session,
        "entry":        trade["entry"],
        "stop_loss":    trade["stop_loss"],
        "tp1":          trade["tp1"],
        "tp2":          trade["tp2"],
        "tp3":          trade.get("tp3"),
        "lot_size":     trade["lot_size"],
        "atr":          trade["atr"],
        "rsi":          round(rsi, 1),
        "adx":          round(adx, 1) if not pd.isna(adx) else None,
        "di_diff":      round(current.get("di_diff", 0), 1),
        "macd_hist":    round(current["macd_hist"], 4) if current.get("macd_hist") and not pd.isna(current["macd_hist"]) else None,
        "vol_ratio":    round(vol_ratio, 2) if vol_ratio and not pd.isna(vol_ratio) else None,
        "ema_fast":     round(current["ema_fast"], 2),
        "ema_slow":     round(current["ema_slow"], 2),
        "trend":        current["trend_label"],
        "confirmation_trend": trend,
        "rr_tp1":       trade["rr_tp1"],
        "rr_tp2":       trade["rr_tp2"],
        "potential_loss":  trade["potential_loss"],
        "potential_tp1":   trade["potential_tp1"],
        "potential_tp2":   trade["potential_tp2"],
        "sl_distance":     trade["sl_distance"],
        "was_capped":      trade["was_capped"],
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
        print(f"  TP1: ${signal['tp1']} | TP2: ${signal['tp2']} | TP3: {signal.get('tp3', 'N/A')}")
        print(f"  Regime: {signal['regime']} | Session: {signal['session']}")
        print(f"  SuperTrend Dir: {signal.get('supertrend_dir')} | BOS: {signal.get('bos')} | CHoCH: {signal.get('choch')}")
        print(f"  Divergence: {signal.get('divergence')}")
    else:
        opp = check_best_opportunity(gold_1h, ticker="GC=F")
        if opp:
            print(f"  OPPORTUNITY: {opp['direction']} score={opp['signal_score']} regime={opp['regime']}")
        else:
            print("  No signal or opportunity right now")

    status = check_trend_status(gold_1h, ticker="GC=F")
    if status:
        print(f"\n  Status: {status['condition']} | RSI: {status['rsi']} | ADX: {status.get('adx')} | Regime: {status['regime']}")
