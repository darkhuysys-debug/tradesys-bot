"""Signal engine — evaluates indicator data and generates BUY/SELL signals."""

def evaluate_signal(indicators: dict, state) -> tuple[str, int, list[str]]:
    """
    Returns (signal: str, score: int, reasons: list[str])
    signal: "BUY", "SELL", or "NONE"
    score: -100 to 100
    """
    score = 0
    reasons = []
    close = indicators["last_close"]

    # RSI
    rsi_val = indicators["rsi"]
    if rsi_val < state.rsi_oversold:
        score += 20
        reasons.append(f"RSI oversold ({rsi_val:.1f})")
    elif rsi_val > state.rsi_overbought:
        score -= 20
        reasons.append(f"RSI overbought ({rsi_val:.1f})")
    elif rsi_val > 50:
        score += 5
        reasons.append(f"RSI bullish ({rsi_val:.1f})")
    else:
        score -= 5
        reasons.append(f"RSI bearish ({rsi_val:.1f})")

    # MACD
    hist = indicators["macd_histogram"]
    prev_hist = indicators.get("prev_macd_histogram", 0)
    macd_line = indicators["macd_line"]
    macd_signal = indicators["macd_signal"]

    if macd_line > macd_signal and hist > 0:
        score += 20
        reasons.append("MACD bullish crossover")
    elif macd_line < macd_signal and hist < 0:
        score -= 20
        reasons.append("MACD bearish crossover")

    # MACD histogram turning
    if hist > 0 and prev_hist <= 0:
        score += 10
        reasons.append("MACD histogram turning up")
    elif hist < 0 and prev_hist >= 0:
        score -= 10
        reasons.append("MACD histogram turning down")

    # EMA crossover
    ema_f = indicators["ema_fast"]
    ema_s = indicators["ema_slow"]
    prev_ema_f = indicators.get("prev_ema_fast", 0)
    prev_ema_s = indicators.get("prev_ema_slow", 0)

    if ema_f > ema_s and prev_ema_f <= prev_ema_s:
        score += 15
        reasons.append("EMA fast crossed above slow")
    elif ema_f < ema_s and prev_ema_f >= prev_ema_s:
        score -= 15
        reasons.append("EMA fast crossed below slow")
    elif ema_f > ema_s:
        score += 5
    else:
        score -= 5

    # Bollinger Bands
    bb_lower = indicators["bb_lower"]
    bb_upper = indicators["bb_upper"]
    bb_mid = indicators["bb_middle"]

    if bb_lower > 0 and close <= bb_lower:
        score += 15
        reasons.append("Price at BB lower band")
    elif bb_upper > 0 and close >= bb_upper:
        score -= 15
        reasons.append("Price at BB upper band")

    # Volume surge
    vol = indicators.get("volume_sma", 0)
    curr_vol = indicators.get("current_volume", 0)
    if vol > 0 and curr_vol > vol * 1.5:
        if score > 0:
            score += 10
            reasons.append("Volume surge (bullish)")
        elif score < 0:
            score -= 10
            reasons.append("Volume surge (bearish)")

    score = max(-100, min(100, score))

    if score >= 30:
        return "BUY", score, reasons
    elif score <= -30:
        return "SELL", score, reasons
    else:
        return "NONE", score, reasons
