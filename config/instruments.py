"""
Instrument definitions for all markets.
All instruments are FUTURES contracts traded on MetaTrader 5 (Money Plant server).
Covers: Gold, Silver, Crude Oil, Natural Gas, Copper, Brent + NIFTY F&O Stocks + Indices.

NOTE: yfinance does NOT have Indian futures data (NSE F&O / MCX).
For Indian stocks, spot prices (.NS) are used as proxy - spot and futures
move identically for signal generation purposes.
"""

# --- Commodity FUTURES (yfinance futures tickers) ---
COMMODITIES = {
    "GOLD": {
        "name": "Gold Futures (XAUUSD)",
        "yf_ticker": "GC=F",
        "yf_ticker_alt": "XAUUSD=X",
        "contract_size": 100,     # 1 lot = 100 troy ounces
        "pip_value_per_lot": 1.0,
        "dollar_per_1_move": 100, # $100 per $1.00 price move per lot
        "currency": "USD",
        "market": "COMEX",
        "timeframe": "1h",
        "min_lot": 0.01,
    },
    "SILVER": {
        "name": "Silver Futures (XAGUSD)",
        "yf_ticker": "SI=F",
        "yf_ticker_alt": "XAGUSD=X",
        "contract_size": 5000,    # 1 lot = 5000 troy ounces
        "pip_value_per_lot": 5.0,
        "dollar_per_1_move": 5000,
        "currency": "USD",
        "market": "COMEX",
        "timeframe": "1h",
        "min_lot": 0.01,
    },
    "CRUDE_OIL": {
        "name": "Crude Oil Futures (WTI)",
        "yf_ticker": "CL=F",
        "contract_size": 1000,    # 1 lot = 1000 barrels
        "pip_value_per_lot": 10.0,
        "dollar_per_1_move": 1000,
        "currency": "USD",
        "market": "NYMEX",
        "timeframe": "1h",
        "min_lot": 0.01,
    },
    "BRENT_CRUDE": {
        "name": "Brent Crude Futures",
        "yf_ticker": "BZ=F",
        "contract_size": 1000,
        "pip_value_per_lot": 10.0,
        "dollar_per_1_move": 1000,
        "currency": "USD",
        "market": "ICE",
        "timeframe": "1h",
        "min_lot": 0.01,
    },
    "NATURAL_GAS": {
        "name": "Natural Gas Futures",
        "yf_ticker": "NG=F",
        "contract_size": 10000,   # 1 lot = 10,000 MMBtu
        "pip_value_per_lot": 10.0,
        "dollar_per_1_move": 10000,
        "currency": "USD",
        "market": "NYMEX",
        "timeframe": "1h",
        "min_lot": 0.01,
    },
    "COPPER": {
        "name": "Copper Futures",
        "yf_ticker": "HG=F",
        "contract_size": 25000,   # 1 lot = 25,000 lbs
        "pip_value_per_lot": 2.5,
        "dollar_per_1_move": 25000,
        "currency": "USD",
        "market": "COMEX",
        "timeframe": "1h",
        "min_lot": 0.01,
    },
    "PLATINUM": {
        "name": "Platinum Futures",
        "yf_ticker": "PL=F",
        "contract_size": 50,      # 1 lot = 50 troy ounces
        "pip_value_per_lot": 0.5,
        "dollar_per_1_move": 50,
        "currency": "USD",
        "market": "NYMEX",
        "timeframe": "1h",
        "min_lot": 0.01,
    },
}

# --- Indian Indices (Spot - used for trend confirmation) ---
# NOTE: Futures tickers not available on yfinance for NSE
INDICES = {
    "NIFTY50": {
        "name": "NIFTY 50 Futures",
        "yf_ticker": "^NSEI",        # Spot proxy (futures data not on yfinance)
        "currency": "INR",
        "market": "NSE",
        "timeframe": "1d",
    },
    "BANKNIFTY": {
        "name": "BANK NIFTY Futures",
        "yf_ticker": "^NSEBANK",     # Spot proxy (futures data not on yfinance)
        "currency": "INR",
        "market": "NSE",
        "timeframe": "1d",
    },
}

# --- NIFTY 50 Stocks ---
NIFTY_50 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "TITAN.NS", "SUNPHARMA.NS", "ULTRACEMCO.NS", "NTPC.NS", "WIPRO.NS",
    "NESTLEIND.NS", "TMPV.NS", "TATASTEEL.NS", "HCLTECH.NS", "POWERGRID.NS",
    "M&M.NS", "JSWSTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS", "TECHM.NS",
    "INDUSINDBK.NS", "BAJAJFINSV.NS", "ONGC.NS", "HDFCLIFE.NS", "COALINDIA.NS",
    "BRITANNIA.NS", "BAJAJ-AUTO.NS", "CIPLA.NS", "EICHERMOT.NS", "DIVISLAB.NS",
    "DRREDDY.NS", "HEROMOTOCO.NS", "APOLLOHOSP.NS", "TATACONSUM.NS", "GRASIM.NS",
    "SBILIFE.NS", "BPCL.NS", "SHRIRAMFIN.NS", "HINDALCO.NS", "LTIM.NS",
]

# --- NIFTY Next 50 Stocks ---
NIFTY_NEXT_50 = [
    "ABBOTINDIA.NS", "ADANIGREEN.NS", "ADANIPOWER.NS", "AMBUJACEM.NS", "ATGL.NS",
    "AUROPHARMA.NS", "BAJAJHLDNG.NS", "BANKBARODA.NS", "BEL.NS", "BERGEPAINT.NS",
    "BOSCHLTD.NS", "CANBK.NS", "CHOLAFIN.NS", "COLPAL.NS", "CONCOR.NS",
    "DABUR.NS", "DLF.NS", "GODREJCP.NS", "HAVELLS.NS", "ICICIPRULI.NS",
    "IDEA.NS", "IDFCFIRSTB.NS", "IGL.NS", "INDHOTEL.NS", "INDUSTOWER.NS",
    "IRCTC.NS", "JIOFIN.NS", "LICI.NS", "LUPIN.NS", "MARICO.NS",
    "MAXHEALTH.NS", "UNITDSPR.NS", "MOTHERSON.NS", "NAUKRI.NS", "NHPC.NS",
    "OFSS.NS", "PAGEIND.NS", "PFC.NS", "PIDILITIND.NS", "PNB.NS",
    "POLYCAB.NS", "RECLTD.NS", "SBICARD.NS", "SIEMENS.NS", "SRF.NS",
    "TATACOMM.NS", "TATAPOWER.NS", "TORNTPHARM.NS", "TRENT.NS", "ETERNAL.NS",
]

# Combined NIFTY 100
NIFTY_100 = NIFTY_50 + NIFTY_NEXT_50

# All stock tickers for scanning
ALL_STOCK_TICKERS = NIFTY_100

# All commodity tickers
ALL_COMMODITY_TICKERS = [v["yf_ticker"] for v in COMMODITIES.values()]

# All index tickers
ALL_INDEX_TICKERS = [v["yf_ticker"] for v in INDICES.values()]

# Everything combined
ALL_TICKERS = ALL_COMMODITY_TICKERS + ALL_INDEX_TICKERS + ALL_STOCK_TICKERS


def get_commodity_info(ticker):
    """Get commodity info by yfinance ticker."""
    for key, info in COMMODITIES.items():
        if ticker in (info["yf_ticker"], info.get("yf_ticker_alt", "")):
            return info
    return None


def get_instrument_type(ticker):
    """Determine if ticker is commodity, index, or stock."""
    if ticker in ALL_COMMODITY_TICKERS:
        return "commodity"
    if ticker in ALL_INDEX_TICKERS:
        return "index"
    if ticker in ALL_STOCK_TICKERS:
        return "stock"
    return "unknown"


def get_display_name(ticker):
    """Get human-readable name for a ticker."""
    for info in COMMODITIES.values():
        if ticker in (info["yf_ticker"], info.get("yf_ticker_alt", "")):
            return info["name"]
    for info in INDICES.values():
        if ticker == info["yf_ticker"]:
            return info["name"]
    # For stocks, strip .NS suffix
    if ticker.endswith(".NS"):
        return ticker.replace(".NS", "")
    return ticker
