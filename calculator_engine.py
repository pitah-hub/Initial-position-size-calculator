import math

# ---------------------------------------------------------------
# YOUR RULES (edit these numbers, use None to switch a rule off)
# MAX_RISK_PER_TRADE : most you will lose if a trade hits its stop ($),
#                      fees included
# DAILY_LOSS_LIMIT   : your own daily loss limit ($). Keep it BELOW the
#                      prop firm's limit so slippage and floating losses
#                      do not push you over it.
# MAINTENANCE_MARGIN_RATE : used for the liquidation estimate. This is an
#                      assumption, check your exchange or broker.
# ---------------------------------------------------------------
MAX_RISK_PER_TRADE = 100.0
DAILY_LOSS_LIMIT = 300.0
MAINTENANCE_MARGIN_RATE = 0.005

# ---------------------------------------------------------------
# MARKET PROFILES
# contract  : units in 1 lot (1 for crypto and stocks)
# step      : smallest size increment allowed
# quote     : how the loss is converted to USD
# leveraged : True = ask for leverage, show margin and liquidation
# fees      : charged on the FULL trade value, each side
#   entry_pct  % for the entry order (market order = taker)
#   tp_pct     % for take-profit exits (limit order = maker)
#   stop_pct   % for the stop exit (stop-market = taker)
#   per_lot    $ commission per lot per side (forex Raw accounts)
# The crypto fees are EXAMPLE numbers. Replace them with the ones on
# your exchange's fee page. Forex spread is not included.
# ---------------------------------------------------------------
NO_FEES = {"entry_pct": 0.0, "tp_pct": 0.0, "stop_pct": 0.0, "per_lot": 0.0}

MARKETS = {
    "1": {"name": "Forex, USD is quote (EURUSD, GBPUSD, AUDUSD)",
          "contract": 100000, "step": 0.01, "unit": "lots",
          "quote": "usd", "leveraged": True, "fees": dict(NO_FEES)},
    "2": {"name": "Forex, USD is base (USDJPY, USDCAD, USDCHF)",
          "contract": 100000, "step": 0.01, "unit": "lots",
          "quote": "base_usd", "leveraged": True, "fees": dict(NO_FEES)},
    "3": {"name": "Forex cross, quote is GBP/AUD/NZD (EURGBP, AUDNZD)",
          "contract": 100000, "step": 0.01, "unit": "lots",
          "quote": "cross_direct", "leveraged": True, "fees": dict(NO_FEES)},
    "4": {"name": "Forex cross, quote is JPY/CAD/CHF (EURJPY, GBPCAD)",
          "contract": 100000, "step": 0.01, "unit": "lots",
          "quote": "cross_inverse", "leveraged": True, "fees": dict(NO_FEES)},
    "5": {"name": "Gold (XAUUSD)",
          "contract": 100, "step": 0.01, "unit": "lots",
          "quote": "usd", "leveraged": True, "fees": dict(NO_FEES)},
    "6": {"name": "Crypto (BTC, ETH, etc.)",
          "contract": 1, "step": 0.0001, "unit": "coins",
          "quote": "usd", "leveraged": True,
          "fees": {"entry_pct": 0.06, "tp_pct": 0.02, "stop_pct": 0.06, "per_lot": 0.0}},
    "7": {"name": "Stocks",
          "contract": 1, "step": 1, "unit": "shares",
          "quote": "usd", "leveraged": False, "fees": dict(NO_FEES)},
}


# --------------------------- calculation ---------------------------
def _positive(name, value):
    if value is None or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive number.")


def calculate(market, balance, risk_pct, entry, stop, targets,
              conv_rate=None, leverage=1.0,
              max_risk_per_trade=None, daily_limit=None, loss_today=0.0,
              move_sl_to_be=True,
              maintenance_margin_rate=MAINTENANCE_MARGIN_RATE):
    """
    Pure calculation. No input() or print(), so Streamlit or a bot can reuse it.
    targets = [(price, percent_of_position_to_close), ...], percents add up to 100.
    The risk figure is the WORST-CASE LOSS including fees.
    """
    for name, value in (("Balance", balance), ("Risk %", risk_pct),
                        ("Entry", entry), ("Stop loss", stop),
                        ("Leverage", leverage)):
        _positive(name, value)
    if risk_pct > 100:
        raise ValueError("Risk % cannot be above 100.")
    if entry == stop:
        raise ValueError("Entry and stop loss cannot be the same price.")
    if not targets:
        raise ValueError("At least one take profit is required.")
    if max_risk_per_trade is not None:
        _positive("Max risk per trade", max_risk_per_trade)
    if daily_limit is not None:
        _positive("Daily loss limit", daily_limit)
        if loss_today is None or not math.isfinite(loss_today) or loss_today < 0:
            raise ValueError("Loss today must be 0 or more.")
    if not math.isfinite(maintenance_margin_rate) or not 0 <= maintenance_margin_rate < 1:
        raise ValueError("Maintenance margin rate must be between 0 and 1.")

    long_trade = stop < entry
    direction = "LONG" if long_trade else "SHORT"
    risk_per_unit = abs(entry - stop)

    # Targets: profit side of entry, each one further than the last, percents = 100
    previous, total_pct = entry, 0.0
    for price, pct in targets:
        _positive("Target price", price)
        _positive("Target %", pct)
        beyond = price > previous if long_trade else price < previous
        if not beyond:
            raise ValueError("Targets must be on the profit side of entry, "
                             "each one further than the last.")
        previous = price
        total_pct += pct
    if abs(total_pct - 100.0) > 1e-6:
        raise ValueError("Target percentages must add up to 100.")

    # USD value of 1 unit of the quote currency at a given price
    mode = market["quote"]
    if mode in ("cross_direct", "cross_inverse"):
        _positive("Conversion rate", conv_rate)

    def q_at(price):
        if mode == "usd":
            return 1.0
        if mode == "base_usd":
            return 1.0 / price
        if mode == "cross_direct":
            return conv_rate
        if mode == "cross_inverse":
            return 1.0 / conv_rate
        raise ValueError(f"Unknown quote mode: {mode}")

    contract, step = market["contract"], market["step"]
    fees = {**NO_FEES, **market.get("fees", {})}

    def entry_fee(size):
        return (fees["entry_pct"] / 100.0 * size * contract * entry * q_at(entry)
                + fees["per_lot"] * size)

    def exit_fee(size, price, pct):
        return (pct / 100.0 * size * contract * price * q_at(price)
                + fees["per_lot"] * size)

    # Risk in dollars, then apply your rules
    planned_risk = balance * risk_pct / 100.0
    dollar_risk = planned_risk
    capped_by = []
    if max_risk_per_trade is not None and dollar_risk > max_risk_per_trade:
        dollar_risk = max_risk_per_trade
        capped_by.append(f"max risk per trade (${max_risk_per_trade:,.2f})")
    remaining = None
    if daily_limit is not None:
        remaining = daily_limit - loss_today
        if remaining <= 0:
            raise ValueError("Daily loss limit reached. No new trades today.")
        if dollar_risk > remaining:
            dollar_risk = remaining
            capped_by.append(f"daily loss limit (${remaining:,.2f} left today)")

    # Size from the stop distance. Loss per 1 lot (or coin, or share) if the
    # stop hits = price move + entry fee + stop exit fee. Rounded DOWN.
    q_stop = q_at(stop)
    loss_per_size = (contract * risk_per_unit * q_stop
                     + entry_fee(1.0) + exit_fee(1.0, stop, fees["stop_pct"]))
    size_exact = dollar_risk / loss_per_size
    size = round(math.floor(size_exact / step + 1e-9) * step, 8)
    actual_loss = size * loss_per_size
    units = size * contract
    notional = units * entry * q_at(entry)
    margin = notional / leverage

    # Liquidation estimate (isolated margin style, rough)
    liquidation, liq_before_stop = None, False
    if market["leveraged"] and leverage > 1:
        liq_distance = max(entry * (1.0 / leverage - maintenance_margin_rate), 0.0)
        liquidation = entry - liq_distance if long_trade else entry + liq_distance
        liq_before_stop = liq_distance <= risk_per_unit

    # Split the size across targets in whole steps, last target gets the rest
    entry_fee_all = entry_fee(size)
    stages, allocated = [], 0.0
    for i, (price, pct) in enumerate(targets):
        if i < len(targets) - 1:
            stage_size = round(math.floor(size * pct / 100.0 / step + 1e-9) * step, 8)
        else:
            stage_size = round(size - allocated, 8)
        allocated += stage_size
        distance = abs(price - entry)
        gross = stage_size * contract * distance * q_at(price)
        stage_exit_fee = exit_fee(stage_size, price, fees["tp_pct"])
        entry_share = entry_fee_all * stage_size / size if size > 0 else 0.0
        stages.append({
            "price": price, "pct": pct, "size": stage_size,
            "r": distance / risk_per_unit, "gross": gross,
            "exit_fee": stage_exit_fee,
            "profit": gross - stage_exit_fee - entry_share,
        })

    total_net = sum(s["profit"] for s in stages)
    fees_all_hit = entry_fee_all + sum(s["exit_fee"] for s in stages)
    blended_rr = total_net / actual_loss if actual_loss > 0 else 0.0

    # What each outcome is worth, net of fees
    scenarios = [("Stop hit first", -actual_loss)]
    gross_run = fees_run = 0.0
    for i, stage in enumerate(stages[:-1]):
        gross_run += stage["gross"]
        fees_run += stage["exit_fee"]
        rem_size = round(sum(s["size"] for s in stages[i + 1:]), 8)
        if move_sl_to_be:
            rem_exit = exit_fee(rem_size, entry, fees["stop_pct"])
            amount = gross_run - fees_run - rem_exit - entry_fee_all
            label = ("TP1 hit, stop to entry" if i == 0
                     else f"TP1-{i + 1} hit, stop to entry")
        else:
            rem_loss = rem_size * contract * risk_per_unit * q_stop
            rem_exit = exit_fee(rem_size, stop, fees["stop_pct"])
            amount = gross_run - fees_run - rem_loss - rem_exit - entry_fee_all
            label = ("TP1 hit, original stop" if i == 0
                     else f"TP1-{i + 1} hit, original stop")
        scenarios.append((label, amount))
    scenarios.append(("All targets hit", total_net))

    # Best case break-even: every win hits ALL targets, every loss is a full stop
    breakeven = None
    if actual_loss > 0 and total_net > 0:
        breakeven = actual_loss / (actual_loss + total_net) * 100.0
    stopouts_to_limit = None
    if remaining is not None and actual_loss > 0:
        stopouts_to_limit = int(math.floor(remaining / actual_loss + 1e-9))

    return {
        "direction": direction, "planned_risk": planned_risk,
        "dollar_risk": dollar_risk, "capped_by": capped_by,
        "size_exact": size_exact, "size": size, "actual_loss": actual_loss,
        "notional": notional, "margin": margin,
        "liquidation": liquidation, "liq_before_stop": liq_before_stop,
        "stages": stages, "total_net": total_net, "fees_all_hit": fees_all_hit,
        "blended_rr": blended_rr, "scenarios": scenarios,
        "breakeven": breakeven,
        "max_loss_rate": None if breakeven is None else 100.0 - breakeven,
        "remaining_before": remaining, "stopouts_to_limit": stopouts_to_limit,
        "move_sl_to_be": move_sl_to_be,
    }
