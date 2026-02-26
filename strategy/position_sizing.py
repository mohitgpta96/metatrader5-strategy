"""
Position sizing calculator - THE MOST CRITICAL SAFETY MODULE.
Calculates proper lot sizes to prevent catastrophic losses.

Rules:
- Max 1% risk per trade
- Hard cap on lot sizes per $1,000 balance
- Never suggests dangerous position sizes
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import ACCOUNT_BALANCE, RISK_PERCENT, MAX_LOT_PER_1000
from config.instruments import COMMODITIES, get_commodity_info, get_instrument_type


def calculate_lot_size(
    ticker,
    entry_price,
    stop_loss_price,
    account_balance=None,
    risk_percent=None,
):
    """
    Calculate safe lot size for a trade.

    Returns:
        dict with lot_size, risk_amount, potential_loss, potential_gain_tp1/tp2, etc.
        Returns None if calculation fails.
    """
    balance = account_balance or ACCOUNT_BALANCE
    risk_pct = risk_percent or RISK_PERCENT

    sl_distance = abs(entry_price - stop_loss_price)
    if sl_distance == 0:
        return None

    risk_amount = balance * (risk_pct / 100.0)
    inst_type = get_instrument_type(ticker)

    if inst_type == "commodity":
        commodity_info = get_commodity_info(ticker)
        if commodity_info is None:
            return None

        dollar_per_1_move = commodity_info["dollar_per_1_move"]
        min_lot = commodity_info["min_lot"]

        # lot_size = risk_amount / (SL_distance × dollar_per_1_move_per_lot)
        raw_lot = risk_amount / (sl_distance * dollar_per_1_move)

        # Round down to nearest 0.01
        lot_size = max(min_lot, round(raw_lot, 2))

        # SAFETY: Hard cap
        max_lot = (balance / 1000.0) * MAX_LOT_PER_1000
        if lot_size > max_lot:
            lot_size = round(max_lot, 2)

        actual_risk = sl_distance * dollar_per_1_move * lot_size

        return {
            "lot_size": lot_size,
            "risk_amount": round(risk_amount, 2),
            "actual_risk": round(actual_risk, 2),
            "sl_distance": round(sl_distance, 2),
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss_price, 2),
            "max_lot_allowed": round(max_lot, 2),
            "instrument": commodity_info["name"],
            "currency": commodity_info["currency"],
            "was_capped": raw_lot > max_lot,
        }

    elif inst_type == "stock":
        # For Indian stocks on MetaTrader (CFDs), similar lot calculation
        # Assume 1 lot = 1 share equivalent for CFDs
        raw_qty = risk_amount / sl_distance
        qty = max(1, int(raw_qty))

        actual_risk = sl_distance * qty

        return {
            "lot_size": qty,  # quantity for stocks
            "risk_amount": round(risk_amount, 2),
            "actual_risk": round(actual_risk, 2),
            "sl_distance": round(sl_distance, 2),
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss_price, 2),
            "instrument": ticker.replace(".NS", ""),
            "currency": "INR",
            "was_capped": False,
        }

    return None


def calculate_trade_levels(ticker, entry_price, atr, direction="BUY"):
    """
    Calculate complete trade levels: SL, TP1, TP2, and lot size.

    Args:
        ticker: yfinance ticker
        entry_price: current/entry price
        atr: ATR value for the instrument
        direction: "BUY" or "SELL"

    Returns:
        dict with all trade parameters
    """
    from config.settings import SL_ATR_MULTIPLIER, TP1_ATR_MULTIPLIER, TP2_ATR_MULTIPLIER

    if direction == "BUY":
        sl = entry_price - (SL_ATR_MULTIPLIER * atr)
        tp1 = entry_price + (TP1_ATR_MULTIPLIER * atr)
        tp2 = entry_price + (TP2_ATR_MULTIPLIER * atr)
    else:  # SELL
        sl = entry_price + (SL_ATR_MULTIPLIER * atr)
        tp1 = entry_price - (TP1_ATR_MULTIPLIER * atr)
        tp2 = entry_price - (TP2_ATR_MULTIPLIER * atr)

    # Calculate position size
    sizing = calculate_lot_size(ticker, entry_price, sl)
    if sizing is None:
        return None

    sl_distance = abs(entry_price - sl)
    tp1_distance = abs(entry_price - tp1)
    tp2_distance = abs(entry_price - tp2)

    rr_tp1 = tp1_distance / sl_distance if sl_distance > 0 else 0
    rr_tp2 = tp2_distance / sl_distance if sl_distance > 0 else 0

    inst_type = get_instrument_type(ticker)
    lot_size = sizing["lot_size"]

    if inst_type == "commodity":
        commodity_info = get_commodity_info(ticker)
        dpm = commodity_info["dollar_per_1_move"] if commodity_info else 100
        potential_loss = sl_distance * dpm * lot_size
        potential_tp1 = tp1_distance * dpm * lot_size
        potential_tp2 = tp2_distance * dpm * lot_size
    else:
        potential_loss = sl_distance * lot_size
        potential_tp1 = tp1_distance * lot_size
        potential_tp2 = tp2_distance * lot_size

    return {
        "direction": direction,
        "entry": round(entry_price, 2),
        "stop_loss": round(sl, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "atr": round(atr, 2),
        "sl_distance": round(sl_distance, 2),
        "lot_size": lot_size,
        "rr_tp1": round(rr_tp1, 2),
        "rr_tp2": round(rr_tp2, 2),
        "potential_loss": round(potential_loss, 2),
        "potential_tp1": round(potential_tp1, 2),
        "potential_tp2": round(potential_tp2, 2),
        "account_balance": ACCOUNT_BALANCE,
        "risk_percent": RISK_PERCENT,
        "was_capped": sizing.get("was_capped", False),
    }


if __name__ == "__main__":
    print("Position Sizing Calculator Test")
    print("=" * 50)

    # Gold example
    print("\n--- Gold BUY Trade ---")
    gold_trade = calculate_trade_levels("GC=F", entry_price=5140.00, atr=25.00, direction="BUY")
    if gold_trade:
        print(f"  Entry:     ${gold_trade['entry']}")
        print(f"  Stop Loss: ${gold_trade['stop_loss']} (-${gold_trade['sl_distance']})")
        print(f"  TP1:       ${gold_trade['tp1']} [R:R 1:{gold_trade['rr_tp1']}]")
        print(f"  TP2:       ${gold_trade['tp2']} [R:R 1:{gold_trade['rr_tp2']}]")
        print(f"  Lot Size:  {gold_trade['lot_size']}")
        print(f"  Max Loss:  ${gold_trade['potential_loss']}")
        print(f"  TP1 Gain:  ${gold_trade['potential_tp1']}")
        print(f"  TP2 Gain:  ${gold_trade['potential_tp2']}")
        print(f"  Capped:    {gold_trade['was_capped']}")

    # Silver example
    print("\n--- Silver SELL Trade ---")
    silver_trade = calculate_trade_levels("SI=F", entry_price=86.80, atr=3.50, direction="SELL")
    if silver_trade:
        print(f"  Entry:     ${silver_trade['entry']}")
        print(f"  Stop Loss: ${silver_trade['stop_loss']}")
        print(f"  TP1:       ${silver_trade['tp1']} [R:R 1:{silver_trade['rr_tp1']}]")
        print(f"  Lot Size:  {silver_trade['lot_size']}")
        print(f"  Max Loss:  ${silver_trade['potential_loss']}")

    # Stock example
    print("\n--- RELIANCE BUY Trade ---")
    stock_trade = calculate_trade_levels("RELIANCE.NS", entry_price=2850.00, atr=60.00, direction="BUY")
    if stock_trade:
        print(f"  Entry:     Rs {stock_trade['entry']}")
        print(f"  Stop Loss: Rs {stock_trade['stop_loss']}")
        print(f"  TP1:       Rs {stock_trade['tp1']} [R:R 1:{stock_trade['rr_tp1']}]")
        print(f"  Lot Size:  {stock_trade['lot_size']} shares")
        print(f"  Max Loss:  Rs {stock_trade['potential_loss']}")
