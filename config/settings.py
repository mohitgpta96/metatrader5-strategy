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
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

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

# --- Market Hours (IST = UTC+5:30) ---
NSE_OPEN_HOUR_UTC = 3    # 9:15 AM IST ≈ 3:45 AM UTC
NSE_CLOSE_HOUR_UTC = 10  # 3:30 PM IST ≈ 10:00 AM UTC
