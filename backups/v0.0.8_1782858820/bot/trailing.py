"""Trailing Stop Loss — dynamically adjusts SL as price moves in favour."""

def update_trailing_stops(state):
    if not getattr(state, 'trailing_enabled', False):
        return False
    if not hasattr(state, '_trailing_active'):
        state._trailing_active = {}
    for pos in list(state.positions):
        sym = pos.get("symbol", "")
        if not sym:
            continue
        entry = pos.get("entry", 0.0)
        current = pos.get("current", 0.0)
        side = pos.get("side", "LONG")
        if entry <= 0 or current <= 0:
            continue
        sym_key = sym + "_" + side
        trail = state._trailing_active.get(sym_key, {})
        activation_pct = getattr(state, 'trailing_activation_pct', 0.5) / 100.0
        distance_pct = getattr(state, 'trailing_distance_pct', 0.3) / 100.0
        if side == "LONG":
            activation_price = entry * (1 + activation_pct)
            if current >= activation_price:
                new_sl = current * (1 - distance_pct)
                old_sl = trail.get("sl", 0.0)
                if new_sl > old_sl:
                    state._trailing_active[sym_key] = {"sl": new_sl, "activated": True}
                    return True
        else:
            activation_price = entry * (1 - activation_pct)
            if current <= activation_price:
                new_sl = current * (1 + distance_pct)
                old_sl = trail.get("sl", 0.0)
                if old_sl == 0.0 or new_sl < old_sl:
                    state._trailing_active[sym_key] = {"sl": new_sl, "activated": True}
                    return True
    return False
