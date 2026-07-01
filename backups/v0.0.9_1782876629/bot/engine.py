import time
import threading
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from state import state
from bot.indicators import get_indicators
from bot.signal_engine import evaluate_signal
from bot.risk_manager import reset_daily, can_trade
from bot.executor import execute_signal, close_position
from bot.trailing import update_trailing_stops
from bot.multi_tf import analyze_multi_timeframe
from bot.regime import detect_regime


def _demo_loop(stop_event: threading.Event):
    """Demo loop — uses real Bybit public market data, no real trades."""
    from bot.bybit_api import get_ticker, get_klines, get_wallet_balance, get_positions
    symbol = state.pair.replace("/", "")
    timeframe_map = {"1m": "1", "3m": "3", "5m": "5", "15m": "15",
                     "30m": "30", "1h": "60", "2h": "120", "4h": "240"}
    tf = timeframe_map.get(state.timeframe, "15")

    state.add_log("[DEMO] Bot initialized successfully")
    state.add_log("[DEMO] Loading real market data from Bybit public API...")
    time.sleep(0.1)
    state.add_log(f"[DEMO] Strategy loaded: {state.strategy}")
    state.add_log("[DEMO] Starting demo loop (Bybit demo account)...")

    try:
        ticker = get_ticker(symbol, demo=True)
        klines = get_klines(symbol, interval=tf, limit=50, demo=True)
    except Exception as e:
        state.add_log(f"[DEMO] Failed to load market data: {e}", "ERROR")
        state.status = "DATA ERROR"
        return

    price = ticker["price"]
    state.market_price     = price
    state.market_change_24h = ticker["change24h"]
    state.market_high_24h   = ticker["high24h"]
    state.market_low_24h    = ticker["low24h"]
    state.market_volume     = ticker["volume"]

    main_acc = state.get_main_account()
    if main_acc:
        try:
            bal = get_wallet_balance(state.bybit_api_key, state.bybit_api_secret, demo=True)
            main_acc["balance"] = bal
            state.equity = bal
            state.add_log(f"[DEMO] Wallet balance: {bal:.2f} USDT")
        except Exception as e:
            state.add_log(f"[DEMO] Balance fetch failed: {e}", "WARN")
            state.equity = main_acc["balance"]
    else:
        state.equity = 0.0

    tick = 0
    while not stop_event.is_set():
        tick += 1
        try:
            ticker = get_ticker(symbol, demo=True)
            state.market_price     = ticker["price"]
            state.market_change_24h = ticker["change24h"]
            state.market_high_24h   = ticker["high24h"]
            state.market_low_24h    = ticker["low24h"]
            state.market_volume     = round(ticker["volume"], 2)
        except Exception as e:
            state.add_log(f"[DEMO] Ticker error: {e}", "WARN")

        try:
            klines = get_klines(symbol, interval=tf, limit=50, demo=True)
            if len(klines) > 20:
                ind = get_indicators(klines,
                                     rsi_period=state.rsi_period,
                                     macd_fast=state.macd_fast, macd_slow=state.macd_slow,
                                     macd_signal=state.macd_signal,
                                     bb_period=state.bb_period, bb_std=state.bb_std,
                                     ema_fast=state.ema_fast, ema_slow=state.ema_slow)
                ind["current_volume"] = klines[-1]["volume"]
                if len(state.rsi_history) > 0:
                    ind["prev_macd_histogram"] = state.rsi_history[-1].get("macd_histogram", 0)
                    ind["prev_ema_fast"] = state.rsi_history[-1].get("ema_fast", 0)
                    ind["prev_ema_slow"] = state.rsi_history[-1].get("ema_slow", 0)

                signal, score, reasons = evaluate_signal(ind, state)
                state.current_rsi      = round(ind["rsi"], 1)
                state.current_macd     = "Bullish" if ind["macd_histogram"] > 0 else "Bearish"
                state.macd_histogram   = round(ind["macd_histogram"], 2)
                state.current_ema_fast = round(ind["ema_fast"], 1)
                state.current_ema_slow = round(ind["ema_slow"], 1)
                state.bb_upper         = round(ind["bb_upper"], 1)
                state.bb_middle        = round(ind["bb_middle"], 1)
                state.bb_lower         = round(ind["bb_lower"], 1)
                state.signal           = signal
                state.score            = score
                state.signal_reasons   = reasons
                state.rsi_history = (state.rsi_history + [ind])[-20:]

                # Multi-TF analysis
                if state.multi_tf_enabled:
                    try:
                        consensus, consensus_score, tf_sigs = analyze_multi_timeframe(state)
                        state.tf_consensus = consensus
                        state.tf_consensus_score = consensus_score
                        state.tf_signals = tf_sigs
                    except Exception as e:
                        state.add_log(f"[DEMO] Multi-TF error: {e}", "WARN")

                # Regime detection (every 5 ticks)
                if tick % 5 == 0:
                    try:
                        regime_data = detect_regime(klines)
                        state.regime = regime_data["regime"]
                        state.regime_strength = regime_data["strength"]
                        state.regime_adx = regime_data["adx"]
                        state.regime_atr_pct = regime_data["atr_pct"]
                    except Exception as e:
                        state.add_log(f"[DEMO] Regime error: {e}", "WARN")

                main_acc = state.get_main_account()
                if main_acc:
                    state.equity = main_acc["balance"] + sum(p["pnl_usdt"] for p in state.positions)

                if tick % 15 == 0:
                    state.add_log(f"[DEMO] RSI: {state.current_rsi} | Signal: {signal} (score={score})")

                if signal != "NONE" and len(state.positions) < state.max_positions:
                    now = time.time()
                    same_signal = signal == state.last_trade_signal
                    cooldown_active = state.trade_cooldown_until > 0
                    cooldown_expired = not cooldown_active or now >= state.trade_cooldown_until
                    time_since_trade = now - state.last_trade_time
                    allow_retry = same_signal and time_since_trade >= 300
                    can_proceed = (not same_signal) or (cooldown_expired and allow_retry)
                    if can_proceed:
                        ok, _ = can_trade(state)
                        if ok:
                            if execute_signal(state, signal, score, state.market_price):
                                state.last_trade_signal = signal
                                state.last_trade_time = now
                                state.trade_cooldown_until = 0.0
        except Exception as e:
            state.add_log(f"[DEMO] Indicator error: {e}", "WARN")

        try:
            api_positions = get_positions(state.bybit_api_key, state.bybit_api_secret, symbol, demo=True)
            api_positions = [p for p in api_positions if p.get("size", 0) > 0]
            state.positions = api_positions
            total_pnl = sum(p["pnl_usdt"] for p in state.positions)
            state.pnl_usdt = round(total_pnl, 2)
            state.pnl_today = state.pnl_usdt
            state.pnl_history.append(state.pnl_usdt)
            if len(state.pnl_history) > 60:
                state.pnl_history = state.pnl_history[-60:]
        except Exception as e:
            state.add_log(f"[DEMO] Position sync error: {e}", "WARN")

        if state.trailing_enabled and state.positions:
            try:
                update_trailing_stops(state)
            except Exception as e:
                state.add_log(f"[DEMO] Trailing stop error: {e}", "WARN")

        time.sleep(1)


def _real_loop(stop_event: threading.Event):
    """Live Bybit data loop with real trading."""
    from bot.bybit_api import get_ticker, get_wallet_balance, get_positions, get_klines
    api_key    = state.bybit_api_key
    api_secret = state.bybit_api_secret
    symbol     = state.pair.replace("/", "")
    demo = state.mode == "demo"
    state.add_log(f"[{'DEMO' if demo else 'REAL'}] Bot initialized — connecting to Bybit...")

    try:
        bal = get_wallet_balance(api_key, api_secret, demo=demo)
        state.add_log(f"[REAL] Wallet balance: {bal:.2f} USDT")
        if state.accounts:
            state.accounts[0]["balance"] = bal
            state.accounts[0]["connected"] = True
        state.equity = bal
    except Exception as e:
        state.add_log(f"[REAL] Connection failed: {e}", "ERROR")
        state.status = "CONNECTION ERROR"
        return

    timeframe_map = {"1m": "1", "3m": "3", "5m": "5", "15m": "15",
                     "30m": "30", "1h": "60", "2h": "120", "4h": "240"}
    tf = timeframe_map.get(state.timeframe, "15")
    reset_daily(state)

    tick = 0
    while not stop_event.is_set():
        tick += 1
        try:
            ticker = get_ticker(symbol, demo=demo)
            state.market_price     = ticker["price"]
            state.market_change_24h = ticker["change24h"]
            state.market_high_24h   = ticker["high24h"]
            state.market_low_24h    = ticker["low24h"]
            state.market_volume     = round(ticker["volume"], 2)
            state.pnl_history.append(state.pnl_usdt)
            if len(state.pnl_history) > 60:
                state.pnl_history = state.pnl_history[-60:]
        except Exception as e:
            state.add_log(f"[REAL] Ticker error: {e}", "WARN")

        # Fetch klines + indicators every tick
        try:
            klines = get_klines(symbol, interval=tf, limit=50, demo=demo)
            if len(klines) > 20:
                ind = get_indicators(klines,
                                     rsi_period=state.rsi_period,
                                     macd_fast=state.macd_fast, macd_slow=state.macd_slow,
                                     macd_signal=state.macd_signal,
                                     bb_period=state.bb_period, bb_std=state.bb_std,
                                     ema_fast=state.ema_fast, ema_slow=state.ema_slow)
                ind["current_volume"] = klines[-1]["volume"]
                if len(state.rsi_history) > 0:
                    ind["prev_macd_histogram"] = state.rsi_history[-1].get("macd_histogram", 0)
                    ind["prev_ema_fast"] = state.rsi_history[-1].get("ema_fast", 0)
                    ind["prev_ema_slow"] = state.rsi_history[-1].get("ema_slow", 0)

                signal, score, reasons = evaluate_signal(ind, state)
                state.current_rsi      = round(ind["rsi"], 1)
                state.current_macd     = "Bullish" if ind["macd_histogram"] > 0 else "Bearish"
                state.macd_histogram   = round(ind["macd_histogram"], 2)
                state.current_ema_fast = round(ind["ema_fast"], 1)
                state.current_ema_slow = round(ind["ema_slow"], 1)
                state.bb_upper         = round(ind["bb_upper"], 1)
                state.bb_middle        = round(ind["bb_middle"], 1)
                state.bb_lower         = round(ind["bb_lower"], 1)
                state.signal           = signal
                state.score            = score
                state.signal_reasons   = reasons
                state.rsi_history = (state.rsi_history + [ind])[-20:]

                # Multi-TF analysis
                if state.multi_tf_enabled:
                    try:
                        consensus, consensus_score, tf_sigs = analyze_multi_timeframe(state)
                        state.tf_consensus = consensus
                        state.tf_consensus_score = consensus_score
                        state.tf_signals = tf_sigs
                        if consensus != "NONE":
                            signal = consensus
                            state.signal = consensus
                            state.score = consensus_score
                    except Exception as e:
                        state.add_log(f"[REAL] Multi-TF error: {e}", "WARN")

                # Regime detection (every 5 ticks)
                if tick % 5 == 0:
                    try:
                        regime_data = detect_regime(klines)
                        state.regime = regime_data["regime"]
                        state.regime_strength = regime_data["strength"]
                        state.regime_adx = regime_data["adx"]
                        state.regime_atr_pct = regime_data["atr_pct"]
                    except Exception as e:
                        state.add_log(f"[REAL] Regime error: {e}", "WARN")

                # Execute signal
                if signal != "NONE" and len(state.positions) < state.max_positions:
                    now = time.time()
                    same_signal = signal == state.last_trade_signal
                    cooldown_active = state.trade_cooldown_until > 0
                    cooldown_expired = not cooldown_active or now >= state.trade_cooldown_until
                    time_since_trade = now - state.last_trade_time
                    allow_retry = same_signal and time_since_trade >= 300
                    can_proceed = (not same_signal) or (cooldown_expired and allow_retry)
                    if can_proceed:
                        ok, reason = can_trade(state)
                        if ok:
                            if execute_signal(state, signal, score, state.market_price):
                                state.last_trade_signal = signal
                                state.last_trade_time = now
                                state.trade_cooldown_until = 0.0
                        elif tick % 30 == 0:
                            state.add_log(f"[REAL] Trade blocked: {reason}", "WARN")
        except Exception as e:
            state.add_log(f"[REAL] Indicator error: {e}", "WARN")

        # Refresh positions every 3s
        if tick % 3 == 0:
            try:
                from bot.bybit_api import get_positions as _get_positions
                positions = _get_positions(state.bybit_api_key, state.bybit_api_secret, symbol, demo=demo)
                positions = [p for p in positions if abs(float(p.get("size", 0) or 0)) > 1e-9]
                for p in positions:
                    if "pnl_usdt" not in p:
                        p["pnl_usdt"] = 0.0
                state.positions = positions
                total_pnl = sum(p["pnl_usdt"] for p in positions)
                state.pnl_usdt  = round(total_pnl, 2)
                bal = get_wallet_balance(state.bybit_api_key, state.bybit_api_secret, demo=demo)
                state.equity = bal
                if state.accounts:
                    state.accounts[0]["balance"] = bal
            except Exception as e:
                state.add_log(f"[DEMO] Position sync error: {e}", "WARN")

        if state.trailing_enabled and state.positions:
            try:
                update_trailing_stops(state)
            except Exception as e:
                state.add_log(f"[REAL] Trailing stop error: {e}", "WARN")

        if tick % 10 == 0:
            state.add_log(f"[REAL] {symbol}: {state.market_price:.1f} | Signal: {state.signal} ({state.score})")

        time.sleep(1.5)


def start_bot():
    if state.running:
        return
    state.running    = True
    state.status     = "RUNNING"
    state.start_time = time.time()
    state.pid        = os.getpid()
    state.started    = time.strftime("%Y-%m-%d %H:%M:%S")
    state.positions.clear()
    if state.bybit_api_key and state.bybit_api_secret:
        try:
            from bot.bybit_api import get_positions as _get_positions
            symbol = state.pair.replace("/", "")
            demo = state.mode == "demo"
            positions = _get_positions(state.bybit_api_key, state.bybit_api_secret, symbol, demo=demo)
            positions = [p for p in positions if abs(float(p.get("size", 0) or 0)) > 1e-9]
            for p in positions:
                if "pnl_usdt" not in p:
                    p["pnl_usdt"] = 0.0
            state.positions = positions
        except Exception:
            pass
    state.signal     = "NONE"
    state.score      = 0
    state.signal_reasons = []
    state.rsi_history = []
    state.last_trade_signal = "NONE"
    state.last_trade_time = 0.0
    state.trade_cooldown_until = 0.0

    if state.bybit_api_key and state.bybit_api_secret:
        state.add_log(f"[INFO] Position mode config: {state.position_mode.upper()}. Vui long chuyen Position Mode tren Bybit web/app de match.", "INFO")

    stop_event        = threading.Event()
    state._stop_event = stop_event

    target = _real_loop if state.mode == "real" else _demo_loop
    t = threading.Thread(target=target, args=(stop_event,), daemon=True)
    t.start()
    state.bot_thread = t


def stop_bot():
    if not state.running:
        return
    state.running    = False
    state.status     = "STOPPED"
    state.start_time = None
    state.signal     = "NONE"
    state.score      = 0
    state.signal_reasons = []
    state.last_trade_signal = "NONE"
    state.last_trade_time = 0.0
    state.trade_cooldown_until = 0.0
    if hasattr(state, "_stop_event") and state._stop_event:
        state._stop_event.set()
    state.add_log("Bot stopped.")
