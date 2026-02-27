"""
Technical indicator calculations using the 'ta' library.

Full suite — matches and exceeds strategies used by:
  Zerodha Streak, Tradetron, TradingView top algos, Turtle Trading / CTA funds.

Indicators:
  Existing : EMA 20/50, RSI 14, ATR 14, ADX 14, MACD, Bollinger Bands,
             SuperTrend, StochRSI, BOS/CHoCH, Swing H/L, Regime, Session
  New      : Ichimoku Cloud, Parabolic SAR, Donchian Channel (Turtle),
             Hull Moving Average, Rolling VWAP
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
from ta.trend import EMAIndicator, ADXIndicator, MACD, IchimokuIndicator, PSARIndicator
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands, DonchianChannel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD, ADX_PERIOD, VOLUME_MA_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL_PERIOD, BB_PERIOD, BB_STD,
    SUPERTREND_PERIOD, SUPERTREND_MULTIPLIER,
    STOCHRSI_PERIOD, STOCHRSI_SMOOTH_K, STOCHRSI_SMOOTH_D,
    SWING_LOOKBACK,
    ICHIMOKU_TENKAN, ICHIMOKU_KIJUN, ICHIMOKU_SENKOU_B,
    DONCHIAN_PERIOD,
    HMA_FAST, HMA_SLOW,
    VWAP_PERIOD,
    PSAR_STEP, PSAR_MAX_STEP,
)

IST = timezone(timedelta(hours=5, minutes=30))


def add_indicators(df):
    """
    Add all strategy indicators to a DataFrame.

    Input: DataFrame with columns [Open, High, Low, Close, Volume]
    Output: Same DataFrame with added columns:
        Existing: EMA_20, EMA_50, RSI_14, ATR_14, ATR_Percentile, ADX_14,
                  DI_Plus, DI_Minus, DI_Diff, MACD, MACD_Signal, MACD_Hist,
                  BB_Upper, BB_Lower, BB_Mid, BB_Width, BB_Width_MA,
                  Body_Ratio, Vol_Ratio, Trend, EMA_Cross, Regime
        New:      SuperTrend, SuperTrend_Dir,
                  StochRSI_K, StochRSI_D,
                  Swing_High, Swing_Low, BOS, CHoCH
    """
    if df is None or df.empty or len(df) < EMA_SLOW + 10:
        return df

    df = df.copy()

    # Standardize column names
    col_map = {}
    for col in df.columns:
        lower = col.lower()
        if lower == "open":    col_map[col] = "Open"
        elif lower == "high":  col_map[col] = "High"
        elif lower == "low":   col_map[col] = "Low"
        elif lower == "close": col_map[col] = "Close"
        elif lower == "volume":col_map[col] = "Volume"
    if col_map:
        df = df.rename(columns=col_map)

    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]

    # ── EMA ───────────────────────────────────────────────────────────────────
    df[f"EMA_{EMA_FAST}"] = EMAIndicator(close=close, window=EMA_FAST).ema_indicator()
    df[f"EMA_{EMA_SLOW}"] = EMAIndicator(close=close, window=EMA_SLOW).ema_indicator()

    # ── RSI ───────────────────────────────────────────────────────────────────
    df[f"RSI_{RSI_PERIOD}"] = RSIIndicator(close=close, window=RSI_PERIOD).rsi()

    # ── ATR + Percentile ──────────────────────────────────────────────────────
    df[f"ATR_{ATR_PERIOD}"] = AverageTrueRange(
        high=high, low=low, close=close, window=ATR_PERIOD
    ).average_true_range()
    df["ATR_Percentile"] = df[f"ATR_{ATR_PERIOD}"].rolling(window=50).rank(pct=True) * 100

    # ── ADX + DI +/- ─────────────────────────────────────────────────────────
    adx_ind = ADXIndicator(high=high, low=low, close=close, window=ADX_PERIOD)
    df[f"ADX_{ADX_PERIOD}"] = adx_ind.adx()
    df["DI_Plus"]  = adx_ind.adx_pos()
    df["DI_Minus"] = adx_ind.adx_neg()
    df["DI_Diff"]  = abs(df["DI_Plus"] - df["DI_Minus"])

    # ── MACD ──────────────────────────────────────────────────────────────────
    macd_ind = MACD(
        close=close,
        window_fast=MACD_FAST,
        window_slow=MACD_SLOW,
        window_sign=MACD_SIGNAL_PERIOD,
    )
    df["MACD"]        = macd_ind.macd()
    df["MACD_Signal"] = macd_ind.macd_signal()
    df["MACD_Hist"]   = macd_ind.macd_diff()

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    bb = BollingerBands(close=close, window=BB_PERIOD, window_dev=BB_STD)
    df["BB_Upper"]   = bb.bollinger_hband()
    df["BB_Lower"]   = bb.bollinger_lband()
    df["BB_Mid"]     = bb.bollinger_mavg()
    df["BB_Width"]   = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Mid"].replace(0, float("nan"))
    df["BB_Width_MA"]= df["BB_Width"].rolling(window=50).mean()

    # ── Volume MA ─────────────────────────────────────────────────────────────
    if "Volume" in df.columns:
        df[f"Vol_MA_{VOLUME_MA_PERIOD}"] = df["Volume"].rolling(window=VOLUME_MA_PERIOD).mean()
        df["Vol_Ratio"] = df["Volume"] / df[f"Vol_MA_{VOLUME_MA_PERIOD}"]
    else:
        df["Vol_Ratio"] = 1.0

    # ── Candle Body Ratio ─────────────────────────────────────────────────────
    df["Body_Size"]    = abs(df["Close"] - df["Open"])
    df["Candle_Range"] = df["High"] - df["Low"]
    df["Body_Ratio"]   = (
        df["Body_Size"] / df["Candle_Range"].replace(0, float("nan"))
    ).fillna(0.5)

    # ── Trend (EMA20 vs EMA50) ────────────────────────────────────────────────
    ema_fast_col = f"EMA_{EMA_FAST}"
    ema_slow_col = f"EMA_{EMA_SLOW}"
    df["Trend"] = 0
    df.loc[df[ema_fast_col] > df[ema_slow_col], "Trend"] = 1
    df.loc[df[ema_fast_col] < df[ema_slow_col], "Trend"] = -1

    # ── EMA Crossover ─────────────────────────────────────────────────────────
    df["EMA_Cross"] = 0
    prev_trend = df["Trend"].shift(1)
    df.loc[(prev_trend <= 0) & (df["Trend"] == 1),  "EMA_Cross"] = 1
    df.loc[(prev_trend >= 0) & (df["Trend"] == -1), "EMA_Cross"] = -1

    # ── Market Regime ─────────────────────────────────────────────────────────
    df["Regime"] = _classify_regime(df)

    # ── SuperTrend (NEW) ──────────────────────────────────────────────────────
    try:
        st, st_dir = _calculate_supertrend(
            df, period=SUPERTREND_PERIOD, multiplier=SUPERTREND_MULTIPLIER
        )
        df["SuperTrend"]     = st
        df["SuperTrend_Dir"] = st_dir
    except Exception:
        df["SuperTrend"]     = np.nan
        df["SuperTrend_Dir"] = 0

    # ── Stochastic RSI (NEW) ──────────────────────────────────────────────────
    try:
        stochrsi = StochRSIIndicator(
            close=close,
            window=STOCHRSI_PERIOD,
            smooth1=STOCHRSI_SMOOTH_K,
            smooth2=STOCHRSI_SMOOTH_D,
        )
        df["StochRSI_K"] = stochrsi.stochrsi_k()
        df["StochRSI_D"] = stochrsi.stochrsi_d()
    except Exception:
        df["StochRSI_K"] = np.nan
        df["StochRSI_D"] = np.nan

    # ── Swing High / Low + BOS / CHoCH ───────────────────────────────────────
    try:
        df["Swing_High"] = df["High"].rolling(window=SWING_LOOKBACK).max().shift(1)
        df["Swing_Low"]  = df["Low"].rolling(window=SWING_LOOKBACK).min().shift(1)
        df["BOS"]   = _detect_bos(df)
        df["CHoCH"] = _detect_choch(df)
    except Exception:
        df["Swing_High"] = np.nan
        df["Swing_Low"]  = np.nan
        df["BOS"]   = 0
        df["CHoCH"] = 0

    # ── Ichimoku Cloud (NEW — Japanese institutional method) ──────────────────
    # Used by: Asian hedge funds, Zerodha Streak, TradingView top strategies
    try:
        ichi = IchimokuIndicator(
            high=high, low=low,
            window1=ICHIMOKU_TENKAN, window2=ICHIMOKU_KIJUN, window3=ICHIMOKU_SENKOU_B,
            visual=False,
        )
        df["Ichi_Tenkan"]  = ichi.ichimoku_conversion_line()
        df["Ichi_Kijun"]   = ichi.ichimoku_base_line()
        df["Ichi_Senkou_A"]= ichi.ichimoku_a()   # Senkou Span A (computed from current data)
        df["Ichi_Senkou_B"]= ichi.ichimoku_b()   # Senkou Span B

        # Cloud: top and bottom
        cloud_top = df[["Ichi_Senkou_A", "Ichi_Senkou_B"]].max(axis=1)
        cloud_bot = df[["Ichi_Senkou_A", "Ichi_Senkou_B"]].min(axis=1)

        # Price position relative to cloud (1=above, -1=below, 0=inside)
        df["Ichi_Cloud_Bull"] = (df["Ichi_Senkou_A"] > df["Ichi_Senkou_B"]).astype(int)
        df["Ichi_Above_Cloud"]= (close > cloud_top).astype(int)
        df["Ichi_Below_Cloud"]= (close < cloud_bot).astype(int)

        # TK relationship and crossover
        df["Ichi_TK_Bull"]  = (df["Ichi_Tenkan"] > df["Ichi_Kijun"]).astype(int)
        prev_tk             = df["Ichi_TK_Bull"].shift(1)
        df["Ichi_TK_Cross"] = 0
        df.loc[(prev_tk == 0) & (df["Ichi_TK_Bull"] == 1), "Ichi_TK_Cross"] =  1
        df.loc[(prev_tk == 1) & (df["Ichi_TK_Bull"] == 0), "Ichi_TK_Cross"] = -1
    except Exception:
        for col in ["Ichi_Tenkan","Ichi_Kijun","Ichi_Senkou_A","Ichi_Senkou_B"]:
            df[col] = np.nan
        for col in ["Ichi_Cloud_Bull","Ichi_Above_Cloud","Ichi_Below_Cloud",
                    "Ichi_TK_Bull","Ichi_TK_Cross"]:
            df[col] = 0

    # ── Parabolic SAR (NEW — Zerodha Streak #1 indicator, dynamic stop-and-reverse) ──
    try:
        psar_ind = PSARIndicator(
            high=high, low=low, close=close,
            step=PSAR_STEP, max_step=PSAR_MAX_STEP,
        )
        df["PSAR"]     = psar_ind.psar()
        psar_up_flag   = psar_ind.psar_up_indicator().fillna(0)
        psar_down_flag = psar_ind.psar_down_indicator().fillna(0)

        # Direction: 1=bullish (price above SAR), -1=bearish (price below SAR)
        df["PSAR_Dir"] = psar_up_flag.astype(int) - psar_down_flag.astype(int)

        # Flip detection (0→1 = bullish flip, 1→0 = bearish flip)
        prev_up = psar_up_flag.shift(1).fillna(0)
        df["PSAR_Flip"] = 0
        df.loc[(prev_up == 0) & (psar_up_flag == 1), "PSAR_Flip"] =  1
        df.loc[(prev_up == 1) & (psar_up_flag == 0), "PSAR_Flip"] = -1
    except Exception:
        df["PSAR"]      = np.nan
        df["PSAR_Dir"]  = 0
        df["PSAR_Flip"] = 0

    # ── Donchian Channel — Turtle Trading breakout system (NEW) ───────────────
    # System 1: 20-bar high/low breakout. Used by: CTAs, hedge funds, legends.
    try:
        don = DonchianChannel(high=high, low=low, close=close, window=DONCHIAN_PERIOD)
        df["Don_Upper"] = don.donchian_channel_hband()
        df["Don_Lower"] = don.donchian_channel_lband()
        df["Don_Mid"]   = don.donchian_channel_mband()

        # Breakout: close breaks above/below the PREVIOUS bar's Donchian band
        prev_upper = df["Don_Upper"].shift(1)
        prev_lower = df["Don_Lower"].shift(1)
        df["Don_Breakout"] = 0
        df.loc[close > prev_upper, "Don_Breakout"] =  1   # new 20-bar high
        df.loc[close < prev_lower, "Don_Breakout"] = -1   # new 20-bar low
    except Exception:
        df["Don_Upper"]    = np.nan
        df["Don_Lower"]    = np.nan
        df["Don_Mid"]      = np.nan
        df["Don_Breakout"] = 0

    # ── Hull Moving Average — HMA (NEW — less lag than EMA, favored by quants) ─
    try:
        df["HMA_Fast"] = _hull_ma(close, HMA_FAST)
        df["HMA_Slow"] = _hull_ma(close, HMA_SLOW)
        df["HMA_Bull"] = (df["HMA_Fast"] > df["HMA_Slow"]).astype(int)
        prev_hma_bull  = df["HMA_Bull"].shift(1)
        df["HMA_Cross"] = 0
        df.loc[(prev_hma_bull == 0) & (df["HMA_Bull"] == 1),  "HMA_Cross"] =  1
        df.loc[(prev_hma_bull == 1) & (df["HMA_Bull"] == 0), "HMA_Cross"] = -1
    except Exception:
        df["HMA_Fast"]  = np.nan
        df["HMA_Slow"]  = np.nan
        df["HMA_Bull"]  = 0
        df["HMA_Cross"] = 0

    # ── Rolling VWAP (NEW — institutional price anchor, #1 intraday reference) ─
    # Price above VWAP = institutions are net long at average cost or better
    try:
        if "Volume" in df.columns:
            typical = (high + low + close) / 3.0
            tp_vol   = typical * df["Volume"]
            df["VWAP"] = (
                tp_vol.rolling(VWAP_PERIOD).sum()
                / df["Volume"].rolling(VWAP_PERIOD).sum()
            )
            df["VWAP_Bull"] = (close > df["VWAP"]).astype(int)
        else:
            df["VWAP"]      = np.nan
            df["VWAP_Bull"] = 0
    except Exception:
        df["VWAP"]      = np.nan
        df["VWAP_Bull"] = 0

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _calculate_supertrend(df, period=10, multiplier=3.0):
    """
    SuperTrend indicator (ATR-based directional filter).

    Algorithm:
      upper_band = (H+L)/2 + multiplier * ATR
      lower_band = (H+L)/2 - multiplier * ATR

      direction flips bearish→bullish when price closes ABOVE upper band
      direction flips bullish→bearish when price closes BELOW lower band

    Returns:
      (supertrend Series, direction Series)
      direction: 1=bullish (price above ST), -1=bearish (price below ST)
    """
    high_arr  = df["High"].values
    low_arr   = df["Low"].values
    close_arr = df["Close"].values
    n = len(close_arr)

    atr_arr = AverageTrueRange(
        high=df["High"], low=df["Low"], close=df["Close"], window=period
    ).average_true_range().values

    hl2 = (high_arr + low_arr) / 2.0

    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    supertrend  = np.full(n, np.nan)
    direction   = np.zeros(n, dtype=np.int8)

    prev = -1  # index of previous valid bar

    for i in range(n):
        if np.isnan(atr_arr[i]):
            continue

        bu = hl2[i] + multiplier * atr_arr[i]
        bl = hl2[i] - multiplier * atr_arr[i]

        if prev == -1:
            # First valid bar: initialise as bearish
            final_upper[i] = bu
            final_lower[i] = bl
            supertrend[i]  = bu
            direction[i]   = -1
            prev = i
            continue

        p = prev  # previous valid bar index

        # ── Update final bands (only tighten, never widen the active side) ──
        final_upper[i] = bu if (bu < final_upper[p] or close_arr[p] > final_upper[p]) \
                         else final_upper[p]
        final_lower[i] = bl if (bl > final_lower[p] or close_arr[p] < final_lower[p]) \
                         else final_lower[p]

        # ── Determine new direction ──
        if direction[p] == -1:          # was bearish
            if close_arr[i] > final_upper[i]:
                direction[i]  = 1       # flip to bullish
                supertrend[i] = final_lower[i]
            else:
                direction[i]  = -1
                supertrend[i] = final_upper[i]
        else:                           # was bullish
            if close_arr[i] < final_lower[i]:
                direction[i]  = -1      # flip to bearish
                supertrend[i] = final_upper[i]
            else:
                direction[i]  = 1
                supertrend[i] = final_lower[i]

        prev = i

    return pd.Series(supertrend, index=df.index), pd.Series(direction.astype(int), index=df.index)


def _detect_bos(df):
    """
    BOS (Break of Structure) — continuation signal IN the current trend.
      BOS  = 1 : Uptrend + close breaks above previous swing high by >0.3×ATR
      BOS  = -1: Downtrend + close breaks below previous swing low  by >0.3×ATR
    """
    from config.settings import BOS_ATR_THRESHOLD
    atr_col = f"ATR_{ATR_PERIOD}"
    bos = pd.Series(0, index=df.index)

    if "Swing_High" not in df.columns or atr_col not in df.columns:
        return bos

    atr   = df[atr_col].fillna(0)
    trend = df["Trend"].fillna(0) if "Trend" in df.columns else pd.Series(0, index=df.index)

    bos[(trend == 1)  & (df["Close"] > df["Swing_High"] + BOS_ATR_THRESHOLD * atr)] = 1
    bos[(trend == -1) & (df["Close"] < df["Swing_Low"]  - BOS_ATR_THRESHOLD * atr)] = -1
    return bos


def _detect_choch(df):
    """
    CHoCH (Change of Character) — FIRST break AGAINST the prevailing trend.
      CHoCH =  1: Downtrend + close breaks above swing high → early reversal warning
      CHoCH = -1: Uptrend   + close breaks below swing low  → early reversal warning
    """
    from config.settings import BOS_ATR_THRESHOLD
    atr_col = f"ATR_{ATR_PERIOD}"
    choch = pd.Series(0, index=df.index)

    if "Swing_High" not in df.columns or atr_col not in df.columns:
        return choch

    atr   = df[atr_col].fillna(0)
    trend = df["Trend"].fillna(0) if "Trend" in df.columns else pd.Series(0, index=df.index)

    # In downtrend, price breaks above swing high → CHoCH bullish
    choch[(trend == -1) & (df["Close"] > df["Swing_High"] + BOS_ATR_THRESHOLD * atr)] = 1
    # In uptrend, price breaks below swing low → CHoCH bearish
    choch[(trend == 1)  & (df["Close"] < df["Swing_Low"]  - BOS_ATR_THRESHOLD * atr)] = -1
    return choch


def _wma(series, period):
    """
    Weighted Moving Average — linearly-weighted rolling mean.
    More recent bars have higher weight. Foundation for HMA.
    """
    weights = np.arange(1, period + 1, dtype=float)
    wsum    = weights.sum()
    return series.rolling(period).apply(lambda x: np.dot(x, weights) / wsum, raw=True)


def _hull_ma(series, period):
    """
    Hull Moving Average (HMA) — virtually lag-free trend indicator.
    Formula: WMA(2 × WMA(n/2) − WMA(n),  √n)
    Much faster response than EMA; doesn't overshoot like DEMA.
    """
    half   = max(2, period // 2)
    sqrt_p = max(2, int(np.sqrt(period)))
    return _wma(2 * _wma(series, half) - _wma(series, period), sqrt_p)


def _classify_regime(df):
    """
    Market Regime (vectorized):
      TRENDING  — ADX >= 20 AND DI separation >= 5
      SQUEEZE   — BB Width at bottom 15th percentile
      VOLATILE  — ATR > 1.5x 20-bar average AND ADX < 25
      RANGING   — Everything else
    Precedence: VOLATILE > SQUEEZE > TRENDING > RANGING
    """
    adx_col = f"ADX_{ADX_PERIOD}"
    atr_col = f"ATR_{ATR_PERIOD}"
    regime  = pd.Series("RANGING", index=df.index)

    if adx_col not in df.columns:
        return regime

    adx      = df[adx_col].fillna(0)
    di_diff  = df["DI_Diff"].fillna(0) if "DI_Diff" in df.columns else pd.Series(0, index=df.index)
    atr_ma   = df[atr_col].rolling(window=20).mean()
    atr_ratio= (df[atr_col] / atr_ma.replace(0, float("nan"))).fillna(1.0)
    bb_width = df["BB_Width"] if "BB_Width" in df.columns else pd.Series(0.05, index=df.index)
    bb_pct   = bb_width.rolling(window=50).rank(pct=True) * 100

    regime[:]                                       = "RANGING"
    regime[(adx >= 20) & (di_diff >= 5)]            = "TRENDING"
    regime[bb_pct <= 15]                            = "SQUEEZE"
    regime[(atr_ratio > 1.5) & (adx < 25)]         = "VOLATILE"
    return regime


# ─────────────────────────────────────────────────────────────────────────────
# Standalone detection functions (called from signals.py per instrument)
# ─────────────────────────────────────────────────────────────────────────────

def detect_fair_value_gaps(df, lookback=20):
    """
    Fair Value Gaps (FVG) — 3-candle imbalance zones.

    Bullish FVG : candle[i-2].High < candle[i].Low  → gap left behind going up
    Bearish FVG : candle[i-2].Low  > candle[i].High → gap left behind going down

    Returns: {'bull_fvg': [...], 'bear_fvg': [...]}
    Each entry: {'low', 'high', 'age', 'in_zone'}
    Only zones that have NOT been filled by subsequent price action are returned.
    """
    result = {"bull_fvg": [], "bear_fvg": []}
    if df is None or len(df) < 3:
        return result

    high_arr  = df["High"].values
    low_arr   = df["Low"].values
    close_arr = df["Close"].values
    n = len(df)
    current_close = close_arr[-1]

    start = max(2, n - lookback)

    for i in range(start, n - 1):
        # ── Bullish FVG ──
        gap_low  = high_arr[i - 2]
        gap_high = low_arr[i]
        if gap_high > gap_low:
            # Check if still unfilled (no candle since i has low <= gap_low)
            filled = any(low_arr[j] <= gap_low for j in range(i + 1, n))
            if not filled:
                in_zone = (gap_low <= current_close <= gap_high)
                result["bull_fvg"].append({
                    "low": round(float(gap_low), 4),
                    "high": round(float(gap_high), 4),
                    "age": n - 1 - i,
                    "in_zone": in_zone,
                })

        # ── Bearish FVG ──
        gap_high_b = low_arr[i - 2]
        gap_low_b  = high_arr[i]
        if gap_high_b > gap_low_b:
            # Check if still unfilled (no candle since i has high >= gap_high_b)
            filled = any(high_arr[j] >= gap_high_b for j in range(i + 1, n))
            if not filled:
                in_zone = (gap_low_b <= current_close <= gap_high_b)
                result["bear_fvg"].append({
                    "low": round(float(gap_low_b), 4),
                    "high": round(float(gap_high_b), 4),
                    "age": n - 1 - i,
                    "in_zone": in_zone,
                })

    # Sort: in_zone first, then youngest first
    result["bull_fvg"].sort(key=lambda x: (not x["in_zone"], x["age"]))
    result["bear_fvg"].sort(key=lambda x: (not x["in_zone"], x["age"]))
    result["bull_fvg"] = result["bull_fvg"][:3]
    result["bear_fvg"] = result["bear_fvg"][:3]
    return result


def detect_order_blocks(df, lookback=30):
    """
    Order Blocks — institutional accumulation/distribution zones.

    Bullish OB: last BEARISH candle before 3 consecutive bullish candles.
    Bearish OB: last BULLISH candle before 3 consecutive bearish candles.

    Returns: {'bull_ob': [...], 'bear_ob': [...]}
    Each entry: {'low', 'high', 'age', 'in_zone'}
    """
    result = {"bull_ob": [], "bear_ob": []}
    if df is None or len(df) < 5:
        return result

    close_arr = df["Close"].values
    open_arr  = df["Open"].values
    high_arr  = df["High"].values
    low_arr   = df["Low"].values
    n = len(df)
    current_close = close_arr[-1]
    start = max(0, n - lookback)

    for i in range(start, n - 3):
        # ── Bullish OB: bearish candle followed by 3 green candles ──
        if (close_arr[i] < open_arr[i] and
                close_arr[i+1] > open_arr[i+1] and
                close_arr[i+2] > open_arr[i+2] and
                close_arr[i+3] > open_arr[i+3]):
            ob_low, ob_high = low_arr[i], high_arr[i]
            if ob_high > ob_low:
                result["bull_ob"].append({
                    "low": round(float(ob_low), 4),
                    "high": round(float(ob_high), 4),
                    "age": n - 1 - i,
                    "in_zone": ob_low <= current_close <= ob_high,
                })

        # ── Bearish OB: bullish candle followed by 3 red candles ──
        if (close_arr[i] > open_arr[i] and
                close_arr[i+1] < open_arr[i+1] and
                close_arr[i+2] < open_arr[i+2] and
                close_arr[i+3] < open_arr[i+3]):
            ob_low, ob_high = low_arr[i], high_arr[i]
            if ob_high > ob_low:
                result["bear_ob"].append({
                    "low": round(float(ob_low), 4),
                    "high": round(float(ob_high), 4),
                    "age": n - 1 - i,
                    "in_zone": ob_low <= current_close <= ob_high,
                })

    result["bull_ob"].sort(key=lambda x: (not x["in_zone"], x["age"]))
    result["bear_ob"].sort(key=lambda x: (not x["in_zone"], x["age"]))
    result["bull_ob"] = result["bull_ob"][:2]
    result["bear_ob"] = result["bear_ob"][:2]
    return result


def detect_divergence(df, lookback=20):
    """
    RSI and MACD divergence detection.

    Bullish divergence: price makes lower low, RSI/MACD makes higher low.
    Bearish divergence: price makes higher high, RSI/MACD makes lower high.

    Returns: {'bull_rsi': bool, 'bear_rsi': bool, 'bull_macd': bool, 'bear_macd': bool}
    Uses 2% price threshold and 2pt RSI / 0.001 MACD histogram threshold
    to avoid noise.
    """
    result = {"bull_rsi": False, "bear_rsi": False, "bull_macd": False, "bear_macd": False}
    rsi_col = f"RSI_{RSI_PERIOD}"
    if rsi_col not in df.columns or len(df) < lookback * 2:
        return result

    close_arr = df["Close"].values
    rsi_arr   = df[rsi_col].values
    n = len(df)

    recent_start = n - lookback
    prior_start  = max(0, recent_start - lookback)
    prior_end    = recent_start

    # Price extremes
    recent_cl_low  = np.nanmin(close_arr[recent_start:n])
    prior_cl_low   = np.nanmin(close_arr[prior_start:prior_end])
    recent_cl_high = np.nanmax(close_arr[recent_start:n])
    prior_cl_high  = np.nanmax(close_arr[prior_start:prior_end])

    # RSI extremes
    recent_rsi_low  = np.nanmin(rsi_arr[recent_start:n])
    prior_rsi_low   = np.nanmin(rsi_arr[prior_start:prior_end])
    recent_rsi_high = np.nanmax(rsi_arr[recent_start:n])
    prior_rsi_high  = np.nanmax(rsi_arr[prior_start:prior_end])

    # Bullish RSI divergence: price lower low + RSI higher low (by margin)
    if recent_cl_low < prior_cl_low * 0.998 and recent_rsi_low > prior_rsi_low + 2.0:
        result["bull_rsi"] = True

    # Bearish RSI divergence: price higher high + RSI lower high
    if recent_cl_high > prior_cl_high * 1.002 and recent_rsi_high < prior_rsi_high - 2.0:
        result["bear_rsi"] = True

    # MACD divergence
    if "MACD_Hist" in df.columns:
        macd_arr = df["MACD_Hist"].values
        recent_macd_low  = np.nanmin(macd_arr[recent_start:n])
        prior_macd_low   = np.nanmin(macd_arr[prior_start:prior_end])
        recent_macd_high = np.nanmax(macd_arr[recent_start:n])
        prior_macd_high  = np.nanmax(macd_arr[prior_start:prior_end])

        if recent_cl_low < prior_cl_low * 0.998 and recent_macd_low > prior_macd_low + 0.0001:
            result["bull_macd"] = True
        if recent_cl_high > prior_cl_high * 1.002 and recent_macd_high < prior_macd_high - 0.0001:
            result["bear_macd"] = True

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Public: get current indicator snapshot + session quality
# ─────────────────────────────────────────────────────────────────────────────

def get_session_quality(market_type="commodity"):
    """
    Classify current time into trading session quality.

    For commodities (Gold/Crude):
      Kill zones: London 02:00-05:00 UTC, New York 07:00-10:00 UTC
      Thin zone:  20:00-01:00 UTC (Asian dead zone)

    For NSE stocks:
      Kill zone: 03:45-05:00 UTC = 09:15-10:30 IST (opening 75 min)
      Thin zone: 09:30-10:00 UTC = 15:00-15:30 IST (last 30 min, choppy)

    Returns: "KILL_ZONE", "NORMAL", or "THIN"
    """
    now = datetime.now(timezone.utc)
    utc_hour = now.hour
    utc_min  = now.minute
    utc_time = utc_hour * 60 + utc_min   # minutes since midnight UTC

    if market_type == "stock":
        # NSE Kill Zone: 03:45–05:00 UTC = 09:15–10:30 IST
        if 3 * 60 + 45 <= utc_time <= 5 * 60:
            return "KILL_ZONE"
        # NSE Thin: 09:30–10:00 UTC = 15:00–15:30 IST
        if 9 * 60 + 30 <= utc_time <= 10 * 60:
            return "THIN"
        return "NORMAL"

    # Commodity (default)
    if 2 <= utc_hour <= 4:
        return "KILL_ZONE"
    if 7 <= utc_hour <= 9:
        return "KILL_ZONE"
    if utc_hour >= 20 or utc_hour <= 1:
        return "THIN"
    return "NORMAL"


def get_current_indicators(df):
    """
    Extract current (latest bar) indicator values from a fully-processed DataFrame.
    Returns a dict with all values including new SuperTrend, StochRSI, BOS/CHoCH fields.
    """
    if df is None or df.empty:
        return None

    latest = df.iloc[-1]
    prev   = df.iloc[-2] if len(df) > 1 else latest

    ema_fast_col = f"EMA_{EMA_FAST}"
    ema_slow_col = f"EMA_{EMA_SLOW}"
    rsi_col      = f"RSI_{RSI_PERIOD}"
    atr_col      = f"ATR_{ATR_PERIOD}"
    adx_col      = f"ADX_{ADX_PERIOD}"

    result = {
        # OHLC
        "close": latest["Close"],
        "open":  latest["Open"],
        "high":  latest["High"],
        "low":   latest["Low"],
        # Trend
        "ema_fast":       latest.get(ema_fast_col),
        "ema_slow":       latest.get(ema_slow_col),
        "rsi":            latest.get(rsi_col),
        "atr":            latest.get(atr_col),
        "atr_percentile": latest.get("ATR_Percentile", 50.0),
        # ADX + directional
        "adx":      latest.get(adx_col),
        "di_plus":  latest.get("DI_Plus"),
        "di_minus": latest.get("DI_Minus"),
        "di_diff":  latest.get("DI_Diff", 0.0),
        # MACD
        "macd":           latest.get("MACD"),
        "macd_signal":    latest.get("MACD_Signal"),
        "macd_hist":      latest.get("MACD_Hist"),
        "prev_macd_hist": prev.get("MACD_Hist"),
        # Bollinger Bands
        "bb_upper":    latest.get("BB_Upper"),
        "bb_lower":    latest.get("BB_Lower"),
        "bb_mid":      latest.get("BB_Mid"),
        "bb_width":    latest.get("BB_Width"),
        "bb_width_ma": latest.get("BB_Width_MA"),
        # Candle quality
        "body_ratio": latest.get("Body_Ratio", 0.5),
        # Volume
        "vol_ratio": latest.get("Vol_Ratio", 1.0),
        # Trend state
        "trend":      int(latest.get("Trend", 0)),
        "ema_cross":  int(latest.get("EMA_Cross", 0)),
        "prev_trend": int(prev.get("Trend", 0)),
        "regime":     latest.get("Regime", "RANGING"),
        # ── NEW: Wave 1 — SMC/ICT ──────────────────────────
        # SuperTrend
        "supertrend":          latest.get("SuperTrend"),
        "supertrend_dir":      int(latest.get("SuperTrend_Dir", 0)),
        "prev_supertrend_dir": int(prev.get("SuperTrend_Dir", 0)),
        # Stochastic RSI (values in [0,1] range)
        "stochrsi_k": latest.get("StochRSI_K"),
        "stochrsi_d": latest.get("StochRSI_D"),
        # Market structure
        "bos":        int(latest.get("BOS", 0)),
        "choch":      int(latest.get("CHoCH", 0)),
        "swing_high": latest.get("Swing_High"),
        "swing_low":  latest.get("Swing_Low"),
        # ── NEW: Wave 2 — Institutional / Turtle ────────────
        # Ichimoku Cloud
        "ichi_tenkan":      latest.get("Ichi_Tenkan"),
        "ichi_kijun":       latest.get("Ichi_Kijun"),
        "ichi_senkou_a":    latest.get("Ichi_Senkou_A"),
        "ichi_senkou_b":    latest.get("Ichi_Senkou_B"),
        "ichi_cloud_bull":  int(latest.get("Ichi_Cloud_Bull", 0)),
        "ichi_above_cloud": int(latest.get("Ichi_Above_Cloud", 0)),
        "ichi_below_cloud": int(latest.get("Ichi_Below_Cloud", 0)),
        "ichi_tk_bull":     int(latest.get("Ichi_TK_Bull", 0)),
        "ichi_tk_cross":    int(latest.get("Ichi_TK_Cross", 0)),
        "prev_ichi_tk_bull":int(prev.get("Ichi_TK_Bull", 0)),
        # Parabolic SAR
        "psar":       latest.get("PSAR"),
        "psar_dir":   int(latest.get("PSAR_Dir", 0)),
        "psar_flip":  int(latest.get("PSAR_Flip", 0)),
        # Donchian Channel
        "don_upper":    latest.get("Don_Upper"),
        "don_lower":    latest.get("Don_Lower"),
        "don_breakout": int(latest.get("Don_Breakout", 0)),
        # Hull MA
        "hma_fast":  latest.get("HMA_Fast"),
        "hma_slow":  latest.get("HMA_Slow"),
        "hma_bull":  int(latest.get("HMA_Bull", 0)),
        "hma_cross": int(latest.get("HMA_Cross", 0)),
        # VWAP
        "vwap":      latest.get("VWAP"),
        "vwap_bull": int(latest.get("VWAP_Bull", 0)),
    }

    if result["trend"] == 1:
        result["trend_label"] = "Bullish"
    elif result["trend"] == -1:
        result["trend_label"] = "Bearish"
    else:
        result["trend_label"] = "Neutral"

    return result


if __name__ == "__main__":
    import yfinance as yf

    print("Testing indicators on Gold (GC=F)...")
    gold = yf.download("GC=F", period="60d", interval="1h", progress=False, auto_adjust=True)

    if isinstance(gold.columns, pd.MultiIndex):
        gold.columns = gold.columns.get_level_values(0)
    gold.columns = [c.title() for c in gold.columns]

    gold = add_indicators(gold)
    current = get_current_indicators(gold)

    if current:
        print(f"\nGold Current Indicators:")
        print(f"  Close:       ${current['close']:.2f}")
        print(f"  EMA 20/50:   ${current['ema_fast']:.2f} / ${current['ema_slow']:.2f}")
        print(f"  RSI:         {current['rsi']:.1f}")
        print(f"  ATR:         ${current['atr']:.2f} (p{current['atr_percentile']:.0f})")
        print(f"  ADX:         {current['adx']:.1f} | DI+: {current['di_plus']:.1f} DI-: {current['di_minus']:.1f}")
        print(f"  MACD Hist:   {current['macd_hist']:.4f}")
        print(f"  Regime:      {current['regime']}")
        print(f"  Session:     {get_session_quality()}")
        print(f"  --- NEW ---")
        print(f"  SuperTrend:  {current['supertrend']:.2f} Dir={current['supertrend_dir']} (prev={current['prev_supertrend_dir']})")
        print(f"  StochRSI K/D:{current['stochrsi_k']:.3f} / {current['stochrsi_d']:.3f}")
        print(f"  BOS:         {current['bos']} | CHoCH: {current['choch']}")
        print(f"  Swing H/L:   {current['swing_high']:.2f} / {current['swing_low']:.2f}")

    # Test standalone detectors
    if gold is not None:
        fvgs = detect_fair_value_gaps(gold)
        obs  = detect_order_blocks(gold)
        divs = detect_divergence(gold)
        print(f"\n  FVG Bull: {len(fvgs['bull_fvg'])} | FVG Bear: {len(fvgs['bear_fvg'])}")
        print(f"  OB  Bull: {len(obs['bull_ob'])}  | OB  Bear: {len(obs['bear_ob'])}")
        print(f"  Divergence: RSI bull={divs['bull_rsi']} bear={divs['bear_rsi']} | MACD bull={divs['bull_macd']} bear={divs['bear_macd']}")
