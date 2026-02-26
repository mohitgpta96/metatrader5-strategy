"""
Technical indicator calculations using the 'ta' library.
Calculates EMA, RSI, ATR for the Triple Confirmation strategy.
"""
import sys
from pathlib import Path

import pandas as pd
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import EMA_FAST, EMA_SLOW, RSI_PERIOD, ATR_PERIOD


def add_indicators(df):
    """
    Add all strategy indicators to a DataFrame.

    Input: DataFrame with columns [Open, High, Low, Close, Volume]
    Output: Same DataFrame with added columns:
        - EMA_20, EMA_50 (trend)
        - RSI_14 (momentum)
        - ATR_14 (volatility)
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

    # EMA (Exponential Moving Average)
    df[f"EMA_{EMA_FAST}"] = EMAIndicator(close=close, window=EMA_FAST).ema_indicator()
    df[f"EMA_{EMA_SLOW}"] = EMAIndicator(close=close, window=EMA_SLOW).ema_indicator()

    # RSI (Relative Strength Index)
    df[f"RSI_{RSI_PERIOD}"] = RSIIndicator(close=close, window=RSI_PERIOD).rsi()

    # ATR (Average True Range)
    df[f"ATR_{ATR_PERIOD}"] = AverageTrueRange(high=high, low=low, close=close, window=ATR_PERIOD).average_true_range()

    # Trend determination
    ema_fast_col = f"EMA_{EMA_FAST}"
    ema_slow_col = f"EMA_{EMA_SLOW}"
    df["Trend"] = 0  # Neutral
    df.loc[df[ema_fast_col] > df[ema_slow_col], "Trend"] = 1   # Bullish
    df.loc[df[ema_fast_col] < df[ema_slow_col], "Trend"] = -1  # Bearish

    # EMA crossover detection
    df["EMA_Cross"] = 0
    prev_trend = df["Trend"].shift(1)
    # Bullish crossover: was bearish/neutral, now bullish
    df.loc[(prev_trend <= 0) & (df["Trend"] == 1), "EMA_Cross"] = 1
    # Bearish crossover: was bullish/neutral, now bearish
    df.loc[(prev_trend >= 0) & (df["Trend"] == -1), "EMA_Cross"] = -1

    return df


def get_current_indicators(df):
    """
    Extract current (latest) indicator values from a DataFrame with indicators.
    Returns a dict with all values.
    """
    if df is None or df.empty:
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    ema_fast_col = f"EMA_{EMA_FAST}"
    ema_slow_col = f"EMA_{EMA_SLOW}"
    rsi_col = f"RSI_{RSI_PERIOD}"
    atr_col = f"ATR_{ATR_PERIOD}"

    result = {
        "close": latest["Close"],
        "open": latest["Open"],
        "high": latest["High"],
        "low": latest["Low"],
        "ema_fast": latest.get(ema_fast_col),
        "ema_slow": latest.get(ema_slow_col),
        "rsi": latest.get(rsi_col),
        "atr": latest.get(atr_col),
        "trend": int(latest.get("Trend", 0)),
        "ema_cross": int(latest.get("EMA_Cross", 0)),
        "prev_trend": int(prev.get("Trend", 0)),
    }

    # Add trend description
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
        print(f"  Close:  ${current['close']:.2f}")
        print(f"  EMA 20: ${current['ema_fast']:.2f}")
        print(f"  EMA 50: ${current['ema_slow']:.2f}")
        print(f"  RSI:    {current['rsi']:.1f}")
        print(f"  ATR:    ${current['atr']:.2f}")
        print(f"  Trend:  {current['trend_label']}")
        print(f"  Cross:  {current['ema_cross']}")
