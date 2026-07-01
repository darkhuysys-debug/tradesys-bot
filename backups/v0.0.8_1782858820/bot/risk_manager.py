"""Risk management — position sizing, daily limits, cooldown."""

import time

def can_trade(state) -> tuple[bool, str]:
    """Check if we're allowed to trade based on risk rules."""
    if not state.get_main_account():
        return False, "No connected account"
    if state.consecutive_losses >= state.max_consecutive_losses:
        return False, f"Max consecutive losses ({state.consecutive_losses})"

    if time.time() < state.cooldown_until:
        remaining = int(state.cooldown_until - time.time())
        return False, f"Cooldown {remaining}s remaining"

    daily_loss_pct = abs(state.daily_pnl) / max(state.equity, 1) * 100
    if state.equity > 0 and daily_loss_pct >= state.max_daily_loss:
        return False, f"Daily loss limit ({state.max_daily_loss}%) reached"

    if state.daily_trades >= state.max_daily_trades:
        return False, f"Daily trade limit ({state.max_daily_trades}) reached"

    return True, "OK"

def calculate_position_size(state, price: float) -> float:
    """Calculate position size based on risk percentage and account equity."""
    risk_amount = state.equity * (state.risk_per_trade / 100)
    sl_distance_pct = state.stop_loss / 100
    if sl_distance_pct <= 0 or price <= 0:
        return 0
    size = risk_amount / (price * sl_distance_pct)
    size = round(size, 3)
    return max(size, 0.001)

def record_trade_result(state, pnl_usdt: float):
    """Update risk state after a trade closes."""
    if pnl_usdt < 0:
        state.consecutive_losses += 1
        state.daily_pnl += pnl_usdt
        if state.consecutive_losses >= state.max_consecutive_losses:
            state.cooldown_until = time.time() + 3600
    else:
        state.consecutive_losses = 0
        state.daily_pnl += pnl_usdt

    state.daily_trades += 1

def reset_daily(state):
    """Reset daily counters."""
    state.daily_trades = 0
    state.daily_pnl = 0.0
    state.consecutive_losses = 0
