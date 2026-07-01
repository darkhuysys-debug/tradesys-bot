"""Market Regime Detection — identifies trend/volatility/sideways conditions."""

import math

def _ema(data, period):
    result = []
    multiplier = 2 / (period + 1)
    for i, v in enumerate(data):
        if i == 0:
            result.append(v)
        else:
            result.append((v - result[-1]) * multiplier + result[-1])
    return result

def _atr(highs, lows, closes, period=14):
    tr = []
    for i in range(len(closes)):
        if i == 0:
            tr.append(highs[i] - lows[i])
        else:
            tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1])))
    return _ema(tr, period)

def _bb_width(closes, period=20, std_dev=2.0):
    if len(closes) < period:
        return 0.0
    window = closes[-period:]
    mid = sum(window) / period
    variance = sum((x - mid) ** 2 for x in window) / period
    std = math.sqrt(variance)
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return (upper - lower) / mid * 100 if mid != 0 else 0

def detect_regime(klines):
    if len(klines) < 20:
        return {"regime": "SIDEWAYS", "strength": 0.0, "adx": 0.0, "bb_width": 0.0, "atr_pct": 0.0}
    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    sma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
    current_price = closes[-1]
    price_vs_sma = (current_price - sma20) / sma20 * 100 if sma20 != 0 else 0
    ema21 = _ema(closes, 21)
    if len(ema21) >= 3:
        ema_slope = (ema21[-1] - ema21[-3]) / abs(ema21[-3]) * 100 if ema21[-3] != 0 else 0
    else:
        ema_slope = 0
    bbw = _bb_width(closes, 20, 2.0)
    atr_vals = _atr(highs, lows, closes, 14)
    atr_pct = (atr_vals[-1] / current_price * 100) if current_price != 0 else 0
    if abs(ema_slope) < 0.05 and bbw < 6:
        regime = "SIDEWAYS"
        strength = max(0, min(1, (6 - bbw) / 6))
    elif abs(ema_slope) < 0.05 and bbw >= 6:
        regime = "VOLATILE"
        strength = min(1, bbw / 15)
    elif ema_slope > 0.05 and price_vs_sma > 0:
        regime = "UPTREND"
        strength = min(1, abs(ema_slope) * 5)
    elif ema_slope < -0.05 and price_vs_sma < 0:
        regime = "DOWNTREND"
        strength = min(1, abs(ema_slope) * 5)
    else:
        regime = "SIDEWAYS"
        strength = 0.3
    return {"regime": regime, "strength": round(strength, 2), "adx": round(abs(ema_slope) * 10, 1), "bb_width": round(bbw, 1), "atr_pct": round(atr_pct, 2)}
