"""
Central configuration for the Multi-Market Trading Signal System.
All settings in one place - easy to tune.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --- Telegram Bot ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")  # Legacy single ID

# Multiple recipients: comma-separated chat IDs and/or channel usernames
# Example: "633478120,987654321,@mt5_signals_channel"
_raw_recipients = os.getenv("TELEGRAM_RECIPIENTS", "")
TELEGRAM_RECIPIENTS = [r.strip() for r in _raw_recipients.split(",") if r.strip()]

# If RECIPIENTS not set, fall back to single CHAT_ID
if not TELEGRAM_RECIPIENTS and TELEGRAM_CHAT_ID:
    TELEGRAM_RECIPIENTS = [TELEGRAM_CHAT_ID]

# --- Account Settings ---
ACCOUNT_BALANCE = float(os.getenv("ACCOUNT_BALANCE", "10000"))
RISK_PERCENT = float(os.getenv("RISK_PERCENT", "1.0"))  # 1% per trade (ultra-safe)

# --- Strategy Parameters ---
EMA_FAST = 20
EMA_SLOW = 50
RSI_PERIOD = 14
ATR_PERIOD = 14

# RSI thresholds for BUY signals
RSI_BUY_MIN = 40
RSI_BUY_MAX = 70

# RSI thresholds for SELL signals
RSI_SELL_MIN = 30
RSI_SELL_MAX = 60

# ATR multipliers for SL/TP
SL_ATR_MULTIPLIER = 1.5
TP1_ATR_MULTIPLIER = 2.0  # R:R = 1:1.33
TP2_ATR_MULTIPLIER = 3.0  # R:R = 1:2.00
TP3_ATR_MULTIPLIER = 4.5  # R:R = 1:3.00 (runner — only for score >= 7)

# --- MACD Settings ---
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL_PERIOD = 9

# --- Bollinger Bands ---
BB_PERIOD = 20
BB_STD = 2

# --- Signal Quality Filters ---
ADX_PERIOD = 14
ADX_MIN_THRESHOLD = 20       # Raised from 15 — ADX<20 = choppy/ranging market
VOLUME_MA_PERIOD = 20        # 20-period moving average of volume
VOLUME_MIN_RATIO = 1.0       # Raised from 0.5 — require at least average volume
MIN_SIGNAL_SCORE = 4         # Only send signals with score >= 4 (out of 10)
CANDLE_BODY_MIN_RATIO = 0.35 # Body must be >= 35% of candle range (filter doji/spinning tops)

# --- Score-Scaled Position Sizing ---
RISK_PERCENT_LOW = 0.5       # Score 1-5 (Trend Opportunity): half risk
RISK_PERCENT_MID = 1.0       # Score 6-8 (normal signals): standard risk
RISK_PERCENT_HIGH = 1.5      # Score 9-10 (high confidence): 1.5x risk

# --- Timeframes ---
PRIMARY_TIMEFRAME = "1h"      # Signal generation
CONFIRMATION_TIMEFRAME = "4h"  # Trend confirmation (used for Gold/Silver only)
STOCK_TIMEFRAME = "1d"        # Indian stocks use daily for more reliable signals

# --- Safety Limits ---
MAX_LOT_PER_1000 = 0.05       # Hard cap: 0.05 lots per $1,000 balance
MAX_OPEN_TRADES = 1            # Only 1 trade at a time
DAILY_LOSS_LIMIT_PERCENT = 3.0   # Stop trading if 3% lost today
WEEKLY_LOSS_LIMIT_PERCENT = 5.0  # Stop trading if 5% lost this week

# --- Data Settings ---
DATA_CACHE_DIR = BASE_DIR / "data" / "cache"
DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_PERIOD_INTRADAY = "60d"  # Max for 1h data on yfinance
HISTORY_PERIOD_DAILY = "1y"      # 1 year daily data for stocks
BACKTEST_PERIOD = "2y"           # 2 years for backtesting (daily data)

# --- Ichimoku Cloud ---
ICHIMOKU_TENKAN  = 9    # Tenkan-sen (conversion line) — short-term trend
ICHIMOKU_KIJUN   = 26   # Kijun-sen  (base line)       — medium-term trend
ICHIMOKU_SENKOU_B= 52   # Senkou Span B (cloud base)   — long-term support/resistance

# --- Donchian Channel (Turtle Trading breakout system) ---
DONCHIAN_PERIOD  = 20   # 20-bar high/low (System 1: fast); 55-bar = System 2 (slow)

# --- Hull Moving Average (HMA) ---
# Faster than EMA, much less lag. Formula: WMA(2*WMA(n/2) - WMA(n), sqrt(n))
HMA_FAST = 9
HMA_SLOW = 16

# --- Rolling VWAP ---
VWAP_PERIOD = 20        # 20-bar volume-weighted average price (institutional price anchor)

# --- Parabolic SAR ---
PSAR_STEP     = 0.02    # Acceleration factor step (standard: 0.02)
PSAR_MAX_STEP = 0.2     # Maximum acceleration factor (standard: 0.2)

# --- SuperTrend ---
SUPERTREND_PERIOD = 10          # ATR period for SuperTrend
SUPERTREND_MULTIPLIER = 3.0     # Band multiplier (higher = fewer flips, less noise)

# --- Stochastic RSI ---
STOCHRSI_PERIOD = 14            # RSI period (applied to RSI, not price directly)
STOCHRSI_SMOOTH_K = 3           # K line smoothing
STOCHRSI_SMOOTH_D = 3           # D line smoothing (signal line)

# --- Market Structure (BOS / CHoCH) ---
SWING_LOOKBACK = 10             # Bars used to define a swing high/low
BOS_ATR_THRESHOLD = 0.3         # Break must exceed swing by at least 0.3x ATR

# --- Fair Value Gap (FVG) ---
FVG_LOOKBACK = 20               # Bars to scan back for unfilled FVG zones

# --- Market Hours ---
# All times in IST (UTC+5:30). Converted to UTC at runtime.

# NSE (Indian Stocks & Indices): Mon-Fri
NSE_OPEN_HOUR = 9
NSE_OPEN_MINUTE = 15
NSE_CLOSE_HOUR = 15
NSE_CLOSE_MINUTE = 30
NSE_DAYS = [0, 1, 2, 3, 4]  # Mon-Fri

# Commodity Futures (COMEX/NYMEX/ICE via Money Plant):
# Global session: Sun 6:00 PM ET - Fri 5:00 PM ET (nearly 24/5)
# In IST: Mon 3:30 AM - Sat 2:30 AM (with daily break 2:30-3:30 AM IST)
COMMODITY_OPEN_HOUR = 3
COMMODITY_OPEN_MINUTE = 30
COMMODITY_CLOSE_HOUR = 2
COMMODITY_CLOSE_MINUTE = 30
# Commodities trade Mon 3:30 AM IST through Sat 2:30 AM IST
COMMODITY_DAYS = [0, 1, 2, 3, 4, 5]  # Mon-Sat (Sat early morning only)
