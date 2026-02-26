# MetaTrader 5 - Multi-Market Futures Signal System
## Project Status: FULLY BUILT & DEPLOYED (Feb 26, 2026)

---

## What We Built

Automated trading signal system jo har ghante 109 futures instruments scan karta hai aur Telegram pe signals bhejta hai.

### Strategy: Triple Confirmation
- **EMA 20/50 Crossover** + **RSI 14 Filter** + **ATR 14 for SL/TP**
- 2 signal types: EMA Crossover + Trend Pullback
- Risk: 1% per trade, position sizing with hard caps
- R:R ratio: TP1 = 1:1.33, TP2 = 1:2.0

---

## Instruments Covered (109 Total)

### Commodity Futures (7) - yfinance futures tickers
| # | Instrument | Ticker | Market | Status |
|---|-----------|--------|--------|--------|
| 1 | Gold Futures (XAUUSD) | GC=F | COMEX | Active |
| 2 | Silver Futures (XAGUSD) | SI=F | COMEX | Active |
| 3 | Crude Oil Futures (WTI) | CL=F | NYMEX | Active |
| 4 | Brent Crude Futures | BZ=F | ICE | Active |
| 5 | Natural Gas Futures | NG=F | NYMEX | Active |
| 6 | Copper Futures | HG=F | COMEX | Active |
| 7 | Platinum Futures | PL=F | NYMEX | Active |

### Index Futures (2) - spot proxy (futures not on yfinance)
| # | Instrument | Ticker | Notes |
|---|-----------|--------|-------|
| 1 | NIFTY 50 Futures | ^NSEI | Spot price used (futures data not available on yfinance) |
| 2 | BANK NIFTY Futures | ^NSEBANK | Spot price used |

### Stock Futures (100) - NIFTY 50 + NIFTY Next 50
- All F&O stocks from NSE
- Spot prices used as proxy (Indian futures not on yfinance)
- Signal applies same to futures since spot ≈ futures price movement

---

## Deployment

### GitHub
- **Repo:** https://github.com/mohitgpta96/metatrader5-strategy
- **Branch:** main
- **Secrets configured:** TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ACCOUNT_BALANCE

### GitHub Actions (Automated Cron Jobs)
| Workflow | Schedule | What it does |
|----------|----------|-------------|
| Market Signal Scanner | Every hour Mon-Fri + Sunday evening | Scans all 109 instruments, sends BUY/SELL signals to Telegram |
| Daily Market Digest | 3:45 PM IST + 11 PM IST | Full market summary with trends, overbought/oversold lists |

### Telegram Bot
- **Bot:** @mohit_mt5_signals_bot ("MT5 Trading Signals")
- **Chat ID:** 633478120
- **Token:** In .env file (NOT in git)
- **Status:** Fully working, delivering signals

---

## Backtest Results (1 Year Data)

| Instrument | Trades | Win Rate | Profit Factor | Return | Max Drawdown |
|-----------|--------|----------|---------------|--------|-------------|
| Gold Futures | 6 | 83.3% | 6.78 | +5.78% | 1.0% |
| Silver Futures | 6 | 83.3% | 5.72 | +4.72% | 1.0% |
| HDFC Bank | 10 | 60.0% | 1.98 | +4.01% | 1.99% |
| Infosys | 15 | 53.3% | 1.52 | +3.63% | 3.94% |
| TCS | 8 | 50.0% | 1.32 | +1.29% | 2.97% |
| Reliance | 7 | 42.9% | 0.84 | -0.62% | 2.66% |

**Verdict:** Strategy has positive edge on Gold/Silver (83% win rate). Indian stocks are mixed - works well on banking/finance, less on volatile stocks.

---

## Today's Live Signals (Feb 26, 2026)

### Commodity Futures BUY Signals
- **Gold Futures (XAUUSD):** Entry $5,197 | SL $5,165 | TP1 $5,239 | Lot 0.03
- **Copper Futures:** Entry $6.03 | SL $5.99 | TP1 $6.08 | Lot 0.11
- **Platinum Futures:** Entry $2,280 | SL $2,243 | TP1 $2,330

### Stock Futures Signals
**BUY:** ICICIBANK FUT, HINDALCO FUT, AUROPHARMA FUT, TATAPOWER FUT
**SELL:** KOTAKBANK FUT, TATACONSUM FUT, SBICARD FUT

### Market Overview
- Gold: $5,197 BULLISH | Silver: $87 BULLISH
- Crude Oil: $64 OVERSOLD | Natural Gas: $2.79 OVERSOLD
- NIFTY: 25,496 BEARISH | BANK NIFTY: 61,187 BULLISH

---

## Project Structure

```
MetaTrader5_strategy/
├── config/
│   ├── settings.py          # Risk params, indicator settings, API keys
│   └── instruments.py       # All 109 instruments (7 commodity + 2 index + 100 stocks)
├── data/
│   └── fetcher.py           # yfinance batch download for all markets
├── strategy/
│   ├── indicators.py        # EMA 20/50, RSI 14, ATR 14 (using 'ta' library)
│   ├── signals.py           # BUY/SELL signal generation (crossover + pullback)
│   └── position_sizing.py   # Lot calculator with safety caps
├── scanner/
│   ├── market_scanner.py    # Multi-market scanner (commodities + stocks + indices)
│   └── daily_digest.py      # Daily summary generator
├── backtest/
│   └── engine.py            # Backtester with equity curve tracking
├── bot/
│   ├── telegram_bot.py      # Telegram message delivery (async)
│   └── formatter.py         # Signal formatting with FUTURES labels
├── docs/
│   └── strategy_guide.html  # Complete strategy guide (dark theme, mobile-friendly)
├── .github/workflows/
│   ├── signal_check.yml     # Hourly scan cron (Mon-Fri + Sunday)
│   └── daily_digest.yml     # Daily digest cron (3:45 PM + 11 PM IST)
├── .env                     # Telegram token + chat ID (NOT in git)
├── .env.example             # Template for .env
├── .gitignore               # Excludes .env, cache, __pycache__
├── requirements.txt         # Dependencies (yfinance, ta, telegram-bot, etc.)
├── run.py                   # CLI entry point
└── PROJECT_STATUS.md        # This file
```

---

## CLI Commands

```bash
# From /Users/mohit/Desktop/MetaTrader5_strategy/

python3 run.py                    # Interactive menu
python3 run.py --scan-all         # Full market scan (console only)
python3 run.py --check-signals    # Scan + send signals to Telegram
python3 run.py --digest           # Generate daily digest
python3 run.py --scan-gold        # Commodities only
python3 run.py --scan-stocks      # NIFTY 100 stocks only
python3 run.py --backtest         # Run backtests
python3 run.py --test-telegram    # Test bot connection
```

---

## Risk Management Settings

| Parameter | Value | Notes |
|-----------|-------|-------|
| Risk per trade | 1% | $100 on $10K account |
| SL distance | 1.5x ATR | Adapts to volatility |
| TP1 | 2.0x ATR | R:R = 1:1.33 |
| TP2 | 3.0x ATR | R:R = 1:2.0 |
| Max lot (Gold) | 0.05 per $1,000 | Hard cap for safety |
| Max open trades | 1 | Focus on quality |
| Daily loss limit | 3% ($300) | STOP trading today |
| Weekly loss limit | 5% ($500) | STOP trading this week |

---

## Known Limitations & Potential Improvements

### yfinance Limitations
1. **No Indian futures data** - NSE F&O and MCX futures not available on yfinance
   - Currently using spot prices as proxy (99% same movement)
   - Could integrate Breeze/Shoonya API for real NSE futures data
2. **yfinance rate limits** - Occasional failures during batch download
3. **1H data limited to 60 days** - Can't backtest more than 60 days on hourly

### Strategy Improvements to Consider
1. **Volume confirmation** - Add volume filter to avoid low-volume signals
2. **Time-of-day filter** - Avoid signals during low-liquidity hours
3. **Multi-timeframe confirmation** - Already have for commodities, need for stocks
4. **Trailing stop loss** - Move SL to breakeven after TP1 hit
5. **Signal cooldown** - Avoid multiple signals on same instrument within X hours
6. **Market regime detection** - Different params for trending vs ranging markets
7. **Correlation filter** - Avoid taking same-direction trades on correlated instruments

### System Improvements to Consider
1. **Signal history database** - Track all past signals and outcomes
2. **Performance tracking** - Win/loss tracking per instrument
3. **Interactive Telegram commands** - /gold, /stocks, /status, /backtest
4. **HTML report** - Auto-generated weekly performance report
5. **Alert sound/priority** - High-priority signals for Gold/Silver
6. **Mobile-friendly dashboard** - Live web dashboard with charts
7. **Paper trading mode** - Auto-track signals without real trades
8. **Webhook integration** - Connect to TradingView for chart overlays

### Infrastructure
1. **Duplicate signal prevention** - Don't send same signal again within X hours
2. **Error alerting** - Notify on Telegram if workflow fails
3. **Data caching** - Reduce API calls with smart caching
4. **Separate Gold/Stock schedules** - Gold 24/5, Stocks only NSE hours

---

## Accounts & Credentials

| Service | Details |
|---------|---------|
| GitHub | mohitgpta96 (mohitgpta96@gmail.com) |
| GitHub Repo | mohitgpta96/metatrader5-strategy |
| Telegram Bot | @mohit_mt5_signals_bot |
| Telegram Chat ID | 633478120 |
| MetaTrader 5 | Money Plant server |
| Account Balance | $10,000 |

---

## Tomorrow's Plan
1. **Analyze** - Review signals accuracy, check if signals match TradingView charts
2. **Paper trade** - Follow signals for 1-2 weeks without real money
3. **Identify improvements** - Based on analysis, prioritize what to build next
4. **Iterate** - Improve strategy based on real market performance
