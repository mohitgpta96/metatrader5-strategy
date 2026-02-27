"""
Technical indicator calculations using the 'ta' library.
Calculates EMA, RSI, ATR, ADX, MACD, Bollinger Bands, Volume MA for signal generation.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pandas as pd
from ta.trend import EMAIndicator, ADXIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD, ADX_PERIOD, VOLUME_MA_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL_PERIOD, BB_PERIOD, BB_STD,
)

IST = timezone(timedelta(hours=5, minutes=30))


def add_indicators(df):
    """
    Add all strategy indicators to a DataFrame.

    Input: DataFrame with columns [Open, High, Low, Close, Volume]
    Output: Same DataFrame with added columns:
        - EMA_20, EMA_50 (trend)
        - RSI_14 (momentum)
        - ATR_14 (volatility) + ATR_Percentile (regime)
        - ADX_14 + DI_Plus + DI_Minus + DI_Diff (trend strength & direction)
        - MACD, MACD_Signal, MACD_Hist (momentum confirmation)
        - BB_Upper, BB_Lower, BB_Mid, BB_Width (volatility bands)
        - Body_Ratio (candle conviction filter)
        - Regime (TRENDING / RANGING / SQUEEZE / VOLATILE)
        - Trend (1=Bullish, -1=Bearish, 0=Neutral)
        - EMA_Cross (1=bullish cross, -1=bearish cross, 0=no cross)
    """
    if df is None or df.empty or len(df) < EMA_SLOW + 10:
        return df

    df = df.copy()

    # Standardize column names
    col_map = {}
    for col in df.columns:
        lower = col.lower()
        if lower == "open":
            col_map[col] = "Open"
        elif lower == "high":
            col_map[col] = "High"
        elif lower == "low":
            col_map[col] = "Low"
        elif lower == "close":
            col_map[col] = "Close"
        elif lower == "volume":
            col_map[col] = "Volume"
    if col_map:
        df = df.rename(columns=col_map)

    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    # --- EMA (Exponential Moving Average) ---
    df[f"EMA_{EMA_FAST}"] = EMAIndicator(close=close, window=EMA_FAST).ema_indicator()
    df[f"EMA_{EMA_SLOW}"] = EMAIndicator(close=close, window=EMA_SLOW).ema_indicator()

    # --- RSI (Relative Strength Index) ---
    df[f"RSI_{RSI_PERIOD}"] = RSIIndicator(close=close, window=RSI_PERIOD).rsi()

    # --- ATR (Average True Range) + Percentile ---
    df[f"ATR_{ATR_PERIOD}"] = AverageTrueRange(
        high=high, low=low, close=close, window=ATR_PERIOD
    ).average_true_range()
    # ATR percentile (0-100): shows if current volatility is high or low vs recent history
    df["ATR_Percentile"] = df[f"ATR_{ATR_PERIOD}"].rolling(window=50).rank(pct=True) * 100

    # --- ADX + DI+ / DI- (Trend Strength + Directional Components) ---
    adx_indicator = ADXIndicator(high=high, low=low, close=close, window=ADX_PERIOD)
    df[f"ADX_{ADX_PERIOD}"] = adx_indicator.adx()
    df["DI_Plus"] = adx_indicator.adx_pos()    # +DI: bullish directional pressure
    df["DI_Minus"] = adx_indicator.adx_neg()   # -DI: bearish directional pressure
    df["DI_Diff"] = abs(df["DI_Plus"] - df["DI_Minus"])  # separation = trend clarity

    # --- MACD (12/26/9) ---
    macd_ind = MACD(
        close=close,
        window_fast=MACD_FAST,
        window_slow=MACD_SLOW,
        window_sign=MACD_SIGNAL_PERIOD,
    )
    df["MACD"] = macd_ind.macd()
    df["MACD_Signal"] = macd_ind.macd_signal()
    df["MACD_Hist"] = macd_ind.macd_diff()   # histogram = MACD line - Signal line

    # --- Bollinger Bands (20/2) ---
    bb = BollingerBands(close=close, window=BB_PERIOD, window_dev=BB_STD)
    df["BB_Upper"] = bb.bollinger_hband()
    df["BB_Lower"] = bb.bollinger_lband()
    df["BB_Mid"] = bb.bollinger_mavg()
    # BB Width: normalized (upper-lower)/mid — low = squeeze, high = expansion
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Mid"].replace(0, float("nan"))
    df["BB_Width_MA"] = df["BB_Width"].rolling(window=50).mean()  # 50-bar average

    # --- Volume Moving Average ---
    if "Volume" in df.columns:
        df[f"Vol_MA_{VOLUME_MA_PERIOD}"] = df["Volume"].rolling(window=VOLUME_MA_PERIOD).mean()
        df["Vol_Ratio"] = df["Volume"] / df[f"Vol_MA_{VOLUME_MA_PERIOD}"]
    else:
        df["Vol_Ratio"] = 1.0

    # --- Candle Body Ratio (conviction filter) ---
    df["Body_Size"] = abs(df["Close"] - df["Open"])
    df["Candle_Range"] = df["High"] - df["Low"]
    df["Body_Ratio"] = (
        df["Body_Size"] / df["Candle_Range"].replace(0, float("nan"))
    ).fillna(0.5)

    # --- Trend (EMA20 vs EMA50) ---
    ema_fast_col = f"EMA_{EMA_FAST}"
    ema_slow_col = f"EMA_{EMA_SLOW}"
    df["Trend"] = 0
    df.loc[df[ema_fast_col] > df[ema_slow_col], "Trend"] = 1    # Bullish
    df.loc[df[ema_fast_col] < df[ema_slow_col], "Trend"] = -1   # Bearish

    # --- EMA Crossover Detection ---
    df["EMA_Cross"] = 0
    prev_trend = df["Trend"].shift(1)
    df.loc[(prev_trend <= 0) & (df["Trend"] == 1), "EMA_Cross"] = 1    # Bullish cross
    df.loc[(prev_trend >= 0) & (df["Trend"] == -1), "EMA_Cross"] = -1  # Bearish cross

    # --- Market Regime Classification ---
    df["Regime"] = _classify_regime(df)

    return df


def _classify_regime(df):
    """
    Classify market regime (vectorized):
      TRENDING  — ADX >= 20 AND DI separation >= 5 (clear directional trend)
      SQUEEZE   — BB Width at bottom 15th percentile (compressed, pre-breakout)
      VOLATILE  — ATR > 1.5x its 20-bar average AND ADX < 25 (unstable/news-driven)
      RANGING   — Everything else (default)

    Order of precedence: VOLATILE > SQUEEZE > TRENDING > RANGING
    """
    adx_col = f"ADX_{ADX_PERIOD}"
    atr_col = f"ATR_{ATR_PERIOD}"

    regime = pd.Series("RANGING", index=df.index)

    if adx_col not in df.columns:
        return regime

    adx = df[adx_col].fillna(0)
    di_diff = df["DI_Diff"].fillna(0) if "DI_Diff" in df.columns else pd.Series(0, index=df.index)

    # ATR volatility spike: current ATR vs 20-bar rolling average
    atr_ma = df[atr_col].rolling(window=20).mean()
    atr_ratio = (df[atr_col] / atr_ma.replace(0, float("nan"))).fillna(1.0)

    # BB Width percentile (50-bar): how compressed is current volatility?
    bb_width = df["BB_Width"] if "BB_Width" in df.columns else pd.Series(0.05, index=df.index)
    bb_width_pct = bb_width.rolling(window=50).rank(pct=True) * 100

    # Apply in order (later rules override earlier)
    regime[:] = "RANGING"
    regime[(adx >= 20) & (di_diff >= 5)] = "TRENDING"
    regime[bb_width_pct <= 15] = "SQUEEZE"
    regime[(atr_ratio > 1.5) & (adx < 25)] = "VOLATILE"

    return regime


def get_session_quality():
    """
    Classify current time into trading session quality for commodities (Gold/Crude).

    Kill zones (best signals):
      London:  02:00-05:00 UTC = 07:30-10:30 IST
      New York: 07:00-10:00 UTC = 12:30-15:30 IST

    Thin zone (worst signals — Asian dead zone):
      20:00-01:00 UTC = 01:30-06:30 IST

    Returns: "KILL_ZONE", "NORMAL", or "THIN"
    """
    utc_hour = datetime.now(timezone.utc).hour

    # London kill zone: 02:00-04:59 UTC
    if 2 <= utc_hour <= 4:
        return "KILL_ZONE"

    # New York kill zone: 07:00-09:59 UTC
    if 7 <= utc_hour <= 9:
        return "KILL_ZONE"

    # Asian thin zone: 20:00-01:59 UTC (low institutional participation)
    if utc_hour >= 20 or utc_hour <= 1:
        return "THIN"

    return "NORMAL"


def get_current_indicators(df):
    """
    Extract current (latest) indicator values from a DataFrame with indicators.
    Returns a dict with all values including new MACD, BB, regime fields.
    """
    if df is None or df.empty:
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    ema_fast_col = f"EMA_{EMA_FAST}"
    ema_slow_col = f"EMA_{EMA_SLOW}"
    rsi_col = f"RSI_{RSI_PERIOD}"
    atr_col = f"ATR_{ATR_PERIOD}"
    adx_col = f"ADX_{ADX_PERIOD}"

    result = {
        "close": latest["Close"],
        "open": latest["Open"],
        "high": latest["High"],
        "low": latest["Low"],
        # Core trend indicators
        "ema_fast": latest.get(ema_fast_col),
        "ema_slow": latest.get(ema_slow_col),
        "rsi": latest.get(rsi_col),
        "atr": latest.get(atr_col),
        "atr_percentile": latest.get("ATR_Percentile", 50.0),
        # ADX + directional
        "adx": latest.get(adx_col),
        "di_plus": latest.get("DI_Plus"),
        "di_minus": latest.get("DI_Minus"),
        "di_diff": latest.get("DI_Diff", 0.0),
        # MACD
        "macd": latest.get("MACD"),
        "macd_signal": latest.get("MACD_Signal"),
        "macd_hist": latest.get("MACD_Hist"),
        "prev_macd_hist": prev.get("MACD_Hist"),   # previous bar histogram (for crossover)
        # Bollinger Bands
        "bb_upper": latest.get("BB_Upper"),
        "bb_lower": latest.get("BB_Lower"),
        "bb_mid": latest.get("BB_Mid"),
        "bb_width": latest.get("BB_Width"),
        "bb_width_ma": latest.get("BB_Width_MA"),
        # Candle quality
        "body_ratio": latest.get("Body_Ratio", 0.5),
        # Volume
        "vol_ratio": latest.get("Vol_Ratio", 1.0),
        # Trend state
        "trend": int(latest.get("Trend", 0)),
        "ema_cross": int(latest.get("EMA_Cross", 0)),
        "prev_trend": int(prev.get("Trend", 0)),
        "regime": latest.get("Regime", "RANGING"),
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
        print(f"  MACD Hist:   {current['macd_hist']:.3f} (prev: {current['prev_macd_hist']:.3f})")
        print(f"  BB Width:    {current['bb_width']:.4f} (avg: {current['bb_width_ma']:.4f})")
        print(f"  Body Ratio:  {current['body_ratio']:.2f}")
        print(f"  Vol Ratio:   {current['vol_ratio']:.2f}")
        print(f"  Regime:      {current['regime']}")
        print(f"  Session:     {get_session_quality()}")
