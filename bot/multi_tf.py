"""Multi-timeframe analysis — evaluates signals across multiple timeframes."""

TIMEFRAME_MAP = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15",
    "30m": "30", "1h": "60", "2h": "120", "4h": "240",
}

def analyze_multi_timeframe(state):
    from bot.bybit_api import get_klines
    from bot.indicators import get_indicators
    from bot.signal_engine import evaluate_signal
    if not getattr(state, 'multi_tf_enabled', False):
        return state.signal, state.score, {}
    symbol = state.pair.replace("/", "")
    tf_list = getattr(state, 'multi_tf_list', ["15m", "1h", "4h"])
    weights = [1.0, 1.5, 2.0]
    total_score = 0.0
    total_weight = 0.0
    tf_signals = {}
    for tf, weight in zip(tf_list, weights[:len(tf_list)]):
        tf_key = TIMEFRAME_MAP.get(tf, "15")
        try:
            klines = get_klines(symbol, interval=tf_key, limit=50, demo=(state.mode == "demo"))
            if len(klines) < 20:
                continue
            ind = get_indicators(klines, rsi_period=state.rsi_period, macd_fast=state.macd_fast, macd_slow=state.macd_slow, macd_signal=state.macd_signal, bb_period=state.bb_period, bb_std=state.bb_std, ema_fast=state.ema_fast, ema_slow=state.ema_slow)
            ind["current_volume"] = klines[-1]["volume"]
            signal, score, reasons = evaluate_signal(ind, state)
            tf_signals[tf] = {"signal": signal, "score": score}
            total_score += score * weight
            total_weight += weight
        except Exception:
            pass
    if total_weight == 0:
        return state.signal, state.score, tf_signals
    avg_score = total_score / total_weight
    if avg_score >= 30:
        consensus = "BUY"
    elif avg_score <= -30:
        consensus = "SELL"
    else:
        consensus = "NONE"
    return consensus, round(avg_score), tf_signals
