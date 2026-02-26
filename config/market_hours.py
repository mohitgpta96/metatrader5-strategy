"""
Market hours checker.
Determines if each market is currently open/live.

Markets:
  - NSE (Indian Stocks & Indices): Mon-Fri 9:15 AM - 3:30 PM IST
  - MCX (Indian Commodities): Mon-Fri 9:00 AM - 11:30 PM IST (summer)
                               Mon-Fri 9:00 AM - 11:55 PM IST (winter, Nov-Mar)
  - Commodity Futures (COMEX/NYMEX): Sun 6 PM ET - Fri 5 PM ET
    In IST: Mon 3:30 AM through Sat 2:30 AM (nearly 24hrs, daily break 2:30-3:30 AM)
"""
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist():
    """Get current time in IST."""
    return datetime.now(IST)


def is_nse_open():
    """
    Check if NSE (Indian stock market) is currently open.
    Open: Mon-Fri, 9:15 AM - 3:30 PM IST.
    """
    now = now_ist()

    # Mon=0 ... Sun=6
    if now.weekday() > 4:  # Saturday or Sunday
        return False

    open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)

    return open_time <= now <= close_time


def is_commodity_open():
    """
    Check if commodity futures market is currently open.
    Global session: Sun 6 PM ET to Fri 5 PM ET.
    In IST: Mon 3:30 AM to Sat 2:30 AM (with daily break ~2:30-3:30 AM IST).

    Simplified: Market is open Mon-Fri anytime EXCEPT the daily break window.
    Saturday before 2:30 AM is also open (Friday night US session).
    Sunday is closed. Saturday after 2:30 AM is closed.
    """
    now = now_ist()
    day = now.weekday()  # Mon=0 ... Sun=6
    hour = now.hour
    minute = now.minute

    # Sunday: fully closed
    if day == 6:
        return False

    # Saturday: only open before 2:30 AM IST (Friday US session ending)
    if day == 5:
        if hour < 2 or (hour == 2 and minute < 30):
            return True
        return False

    # Mon-Fri: open except during daily maintenance break (2:30 AM - 3:30 AM IST)
    if hour == 2 and minute >= 30:
        return False  # break
    if hour == 3 and minute < 30:
        return False  # break

    return True


def is_mcx_open():
    """
    Check if MCX (Indian commodity market) is currently open.
    Non-agri commodities (Gold, Silver, Crude, etc.):
      - Summer (Mar-Nov): Mon-Fri 9:00 AM - 11:30 PM IST
      - Winter (Nov-Mar): Mon-Fri 9:00 AM - 11:55 PM IST
    """
    now = now_ist()

    # Mon=0 ... Sun=6
    if now.weekday() > 4:  # Saturday or Sunday
        return False

    # MCX opens at 9:00 AM IST
    open_time = now.replace(hour=9, minute=0, second=0, microsecond=0)

    # Winter close: 11:55 PM, Summer close: 11:30 PM
    # Use 11:30 PM as safe default (covers both seasons)
    close_time = now.replace(hour=23, minute=30, second=0, microsecond=0)

    return open_time <= now <= close_time


def get_open_markets():
    """
    Get list of currently open markets.
    Returns list of market types: 'commodity', 'mcx_commodity', 'stock', or combinations.
    """
    markets = []
    if is_commodity_open():
        markets.append("commodity")
    if is_mcx_open():
        markets.append("mcx_commodity")
    if is_nse_open():
        markets.append("stock")
    return markets


def market_status_summary():
    """Get a human-readable summary of market status."""
    now = now_ist()
    nse = is_nse_open()
    mcx = is_mcx_open()
    commodity = is_commodity_open()

    lines = [
        f"Time: {now.strftime('%I:%M %p IST')} ({now.strftime('%A')})",
        f"NSE (Stocks/Indices): {'OPEN' if nse else 'CLOSED'}",
        f"MCX (Indian Commodities): {'OPEN' if mcx else 'CLOSED'}",
        f"COMEX/NYMEX (Global Commodities): {'OPEN' if commodity else 'CLOSED'}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(market_status_summary())
    print(f"\nOpen markets: {get_open_markets()}")
