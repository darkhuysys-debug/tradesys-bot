"""Order executor - handles placing orders and managing positions."""

import time

def execute_signal(state, signal: str, score: int, price: float):
    from bot.bybit_api import place_order, set_leverage
    from bot.risk_manager import calculate_position_size, can_trade

    ok, reason = can_trade(state)
    if not ok:
        state.add_log(f"[SKIP] {reason}", "WARN")
        return False

    if not state.bybit_api_key or not state.bybit_api_secret:
        state.add_log("[SKIP] No API credentials configured", "WARN")
        return False

    exchange = getattr(state, "exchange", "bybit")
    symbol = state.pair.replace("/", "")
    side = "Buy" if signal == "BUY" else "Sell"

    existing = [p for p in state.positions if p["symbol"] == state.pair]
    if len(existing) >= state.max_positions:
        state.add_log(f"[SKIP] Max positions ({state.max_positions}) reached", "WARN")
        return False

    size = calculate_position_size(state, price)
    if size <= 0:
        return False

    demo = state.mode == "demo"

    sl_price = None
    tp_price = None
    if state.stop_loss > 0:
        sl_price = price * (1 - state.stop_loss / 100) if signal == "BUY" else price * (1 + state.stop_loss / 100)
    if state.take_profit > 0:
        tp_price = price * (1 + state.take_profit / 100) if signal == "BUY" else price * (1 - state.take_profit / 100)

    if exchange == "okx":
        from bot.okx_api import place_order as okx_place_order, set_leverage as okx_set_leverage
        okx_market = getattr(state, "okx_market", "futures")
        okx_set_leverage(state.okx_api_key, state.okx_api_secret, symbol, state.leverage, market=okx_market)
        position_idx = None
        partial_size = None
        partial_tp_price = None
        if getattr(state, 'partial_tp_enabled', False) and state.take_profit > 0:
            partial_size = size * getattr(state, 'partial_tp_pct', 50.0) / 100.0
            partial_tp_pct = getattr(state, 'partial_tp1_pct', 1.0)
            if signal == "BUY":
                partial_tp_price = price * (1 + partial_tp_pct / 100)
            else:
                partial_tp_price = price * (1 - partial_tp_pct / 100)
        result = okx_place_order(state.okx_api_key, state.okx_api_secret, symbol, side, size,
                                 take_profit=tp_price, stop_loss=sl_price,
                                 market=okx_market)
    else:
        from bot.bybit_api import place_order, set_leverage
        set_leverage(state.bybit_api_key, state.bybit_api_secret, symbol, state.leverage, demo=demo)
        position_idx = None
        if state.position_mode == "hedge":
            position_idx = 0 if signal == "BUY" else 1
        partial_size = None
        partial_tp_price = None
        if getattr(state, 'partial_tp_enabled', False) and state.take_profit > 0:
            partial_size = size * getattr(state, 'partial_tp_pct', 50.0) / 100.0
            partial_tp_pct = getattr(state, 'partial_tp1_pct', 1.0)
            if signal == "BUY":
                partial_tp_price = price * (1 + partial_tp_pct / 100)
            else:
                partial_tp_price = price * (1 - partial_tp_pct / 100)
        result = place_order(state.bybit_api_key, state.bybit_api_secret, symbol, side, size,
                             take_profit=tp_price, stop_loss=sl_price,
                             position_idx=position_idx, demo=demo)
    if "error" in result:
        err = result["error"]
        if "position idx" in err.lower() or "position mode" in err.lower():
            state.add_log(f"[WARN] Mode mismatch. Retry without positionIdx...", "WARN")
            result = place_order(state.bybit_api_key, state.bybit_api_secret, symbol, side, size,
                                 take_profit=tp_price, stop_loss=sl_price,
                                 demo=demo)
            if "error" in result:
                state.add_log(f"[ERROR] Order failed: {result['error']}", "ERROR")
                state.trade_cooldown_until = time.time() + 60
                return False
            state.position_mode = "one-way"
            try:
                from config import load_config, save_config
                cfg = load_config()
                cfg["position_mode"] = "one-way"
                save_config(cfg)
            except Exception:
                pass
            try:
                from bot.bybit_api import switch_position_mode
                switch_res = switch_position_mode(state.bybit_api_key, state.bybit_api_secret, symbol, "one-way", demo=demo)
                if switch_res.get("retCode") == 0:
                    state.add_log("[INFO] Da chuyen tai khoan ve ONE-WAY mode.", "INFO")
                else:
                    state.add_log(f"[WARN] Khong chuyen ve one-way duoc: {switch_res.get('retMsg', 'unknown')}", "WARN")
            except Exception:
                pass
        else:
            state.add_log(f"[ERROR] Order failed: {err}", "ERROR")
            state.trade_cooldown_until = time.time() + 60
            return False

    order_id = result.get("orderId", "?")
    prefix = "[DEMO]" if demo else "[REAL]"
    mode_tag = " [HEDGE]" if state.position_mode == "hedge" else ""
    state.add_log(f"{prefix} {side} {size} {symbol} @ market - Order {order_id}{mode_tag}")
    try:
        from ui.alerts_screen import push_alert
        push_alert(state, "OK", f"{prefix} {side} {size} {symbol} @ {price:.1f} - TP:{state.take_profit}% SL:{state.stop_loss}%")
    except Exception:
        pass
    state.positions = []
    state.trade_cooldown_until = 0.0
    return True

def close_position(state, position: dict):
    exchange = getattr(state, "exchange", "bybit")
    demo = state.mode == "demo"

    if exchange == "okx":
        from bot.okx_api import place_order
        symbol = position["symbol"].replace("/", "")
        side = "Sell" if position["side"] == "LONG" else "Buy"
        size = position.get("size", 0)
        if size <= 0:
            state.trade_cooldown_until = 0.0
            return True
        okx_market = getattr(state, "okx_market", "futures")
        result = place_order(state.okx_api_key, state.okx_api_secret, symbol, side, size,
                             reduce_only=True, market=okx_market)
        if "error" in result:
            state.add_log(f"[ERROR] Close failed: {result['error']}", "ERROR")
            return False
        prefix = "[DEMO]" if demo else "[REAL]"
        state.add_log(f"{prefix} Close {position['side']} {position['symbol']}")
        state.trade_cooldown_until = 0.0
        return True

    if not state.get_main_account():
        return False

    from bot.bybit_api import place_order

    symbol = position["symbol"].replace("/", "")
    side = "Sell" if position["side"] == "LONG" else "Buy"

    if not state.bybit_api_key or not state.bybit_api_secret:
        state.add_log("[SKIP] No API credentials configured", "WARN")
        return False

    size = position.get("size", 0)
    if size <= 0:
        state.trade_cooldown_until = 0.0
        return True

    position_idx = position.get("position_idx", 0)
    result = place_order(state.bybit_api_key, state.bybit_api_secret,
                         symbol, side, size,
                         reduce_only=True, position_idx=position_idx, demo=demo)
    if "error" in result:
        state.add_log(f"[ERROR] Close failed: {result['error']}", "ERROR")
        return False
    prefix = "[DEMO]" if demo else "[REAL]"
    state.add_log(f"{prefix} Close {position['side']} {position['symbol']}")
    state.trade_cooldown_until = 0.0
    return True
