"""Technical indicators — pure Python, no TA-Lib needed."""

def ema(data: list[float], period: int) -> list[float]:
    result = []
    multiplier = 2 / (period + 1)
    for i, v in enumerate(data):
        if i == 0:
            result.append(v)
        else:
            result.append((v - result[-1]) * multiplier + result[-1])
    return result

def sma(data: list[float], period: int) -> list[float]:
    result = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        else:
            result.append(sum(data[i - period + 1:i + 1]) / period)
    return result

def rsi(data: list[float], period: int = 14) -> list[float]:
    deltas = [data[i] - data[i - 1] for i in range(1, len(data))]
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]
    result = [50.0]
    avg_gain = sum(gains[:period]) / period if len(gains) >= period else 0
    avg_loss = sum(losses[:period]) / period if len(losses) >= period else 0
    for i in range(len(deltas)):
        if i < period - 1:
            result.append(50.0)
        elif i == period - 1:
            avg_gain = sum(gains[:period]) / period
            avg_loss = sum(losses[:period]) / period
            rs = avg_gain / avg_loss if avg_loss != 0 else 100
            result.append(100 - (100 / (1 + rs)))
        else:
            avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
            rs = avg_gain / avg_loss if avg_loss != 0 else 100
            result.append(100 - (100 / (1 + rs)))
    return result

def macd(data: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[list, list, list]:
    ema_fast = ema(data, fast)
    ema_slow = ema(data, slow)
    macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(data))]
    signal_line = ema(macd_line, signal)
    histogram = [macd_line[i] - signal_line[i] for i in range(len(data))]
    return macd_line, signal_line, histogram

def bollinger_bands(data: list[float], period: int = 20, std_dev: float = 2.0) -> tuple[list, list, list]:
    import math
    middle = sma(data, period)
    upper = []
    lower = []
    for i in range(len(data)):
        if middle[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            window = data[max(0, i - period + 1):i + 1]
            std = math.sqrt(sum((x - middle[i]) ** 2 for x in window) / len(window))
            upper.append(middle[i] + std_dev * std)
            lower.append(middle[i] - std_dev * std)
    return upper, middle, lower

def volume_sma(volumes: list[float], period: int = 20) -> list:
    return sma(volumes, period)

def get_indicators(klines: list[dict],
                   rsi_period=14,
                   macd_fast=12, macd_slow=26, macd_signal=9,
                   bb_period=20, bb_std=2.0,
                   ema_fast=9, ema_slow=21,
                   volume_ma_period=20) -> dict:
    closes = [k["close"] for k in klines]
    volumes = [k["volume"] for k in klines]

    rsi_vals = rsi(closes, rsi_period)
    macd_line, signal_line, histogram = macd(closes, macd_fast, macd_slow, macd_signal)
    bb_upper, bb_middle, bb_lower = bollinger_bands(closes, bb_period, bb_std)
    ema_fast_vals = ema(closes, ema_fast)
    ema_slow_vals = ema(closes, ema_slow)
    vol_sma_vals = volume_sma(volumes, volume_ma_period)

    return {
        "rsi": rsi_vals[-1] if rsi_vals else 50.0,
        "macd_line": macd_line[-1] if macd_line else 0.0,
        "macd_signal": signal_line[-1] if signal_line else 0.0,
        "macd_histogram": histogram[-1] if histogram else 0.0,
        "bb_upper": bb_upper[-1] if bb_upper[-1] is not None else 0.0,
        "bb_middle": bb_middle[-1] if bb_middle[-1] is not None else 0.0,
        "bb_lower": bb_lower[-1] if bb_lower[-1] is not None else 0.0,
        "ema_fast": ema_fast_vals[-1] if ema_fast_vals else 0.0,
        "ema_slow": ema_slow_vals[-1] if ema_slow_vals else 0.0,
        "volume_sma": vol_sma_vals[-1] if vol_sma_vals else 0.0,
        "last_close": closes[-1] if closes else 0.0,
    }
