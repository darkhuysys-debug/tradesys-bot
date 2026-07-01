import json
import os

CONFIG_DIR = os.path.expanduser("~/.tradesys")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
HISTORY_FILE = os.path.join(CONFIG_DIR, "trade_history.json")

DEFAULT_CONFIG = {
    "mode": "demo",
    "bybit_api_key":    "",
    "bybit_api_secret": "",
    "telegram_bot_token": "",
    "telegram_chat_id":  "",
    "sendgrid_api_key": "",
    "email_from": "",
    "position_mode": "one-way",
    "strategy": {
        "name": "RSI + MACD",
        "pair": "BTC/USDT",
        "timeframe": "15m",
        "risk_per_trade": 1.0,
        "take_profit": 2.0,
        "stop_loss": 1.0,
        "max_positions": 3,
        "risk_mode": "MEDIUM",
        "trailing_enabled": False,
        "trailing_activation_pct": 0.5,
        "trailing_distance_pct": 0.3,
        "partial_tp_enabled": False,
        "partial_tp_pct": 50.0,
        "partial_tp1_pct": 1.0,
        "multi_tf_enabled": False,
        "multi_tf_list": ["15m", "1h", "4h"],
        "rsi_period": 14,
        "rsi_oversold": 30,
        "rsi_overbought": 70,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "ema_fast": 9,
        "ema_slow": 21,
        "bb_period": 20,
        "bb_std": 2.0,
        "volume_ma_period": 20,
        "leverage": 3,
        "cooldown_candles": 3,
        "max_daily_loss": 5.0,
        "max_daily_trades": 5,
    }
}

def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)

def load_config() -> dict:
    ensure_config_dir()
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    cfg.update(saved)
        except Exception:
            pass
    return cfg

def save_config(cfg: dict):
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def save_trade_history(trades: list):
    ensure_config_dir()
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(trades[-500:], f, indent=2)
    except Exception:
        pass

def apply_config_to_state(cfg: dict, state):
    state.mode             = cfg.get("mode", "demo")
    state.bybit_api_key      = cfg.get("bybit_api_key", "")
    state.bybit_api_secret   = cfg.get("bybit_api_secret", "")
    state.telegram_bot_token = cfg.get("telegram_bot_token", "")
    state.telegram_chat_id   = cfg.get("telegram_chat_id", "")
    state.sendgrid_api_key    = cfg.get("sendgrid_api_key", "")
    state.email_from         = cfg.get("email_from", "")
    state.position_mode    = cfg.get("position_mode", "one-way")
    s = cfg.get("strategy", {})
    state.strategy        = s.get("name",           "RSI + MACD")
    state.pair            = s.get("pair",           "BTC/USDT")
    state.timeframe       = s.get("timeframe",      "15m")
    state.risk_per_trade  = s.get("risk_per_trade", 1.0)
    state.take_profit     = s.get("take_profit",    2.0)
    state.stop_loss       = s.get("stop_loss",      1.0)
    state.max_positions   = s.get("max_positions",  3)
    state.risk_mode       = s.get("risk_mode",      "MEDIUM")
    state.rsi_period      = s.get("rsi_period",     14)
    state.rsi_oversold    = s.get("rsi_oversold",   30)
    state.rsi_overbought  = s.get("rsi_overbought", 70)
    state.macd_fast       = s.get("macd_fast",      12)
    state.macd_slow       = s.get("macd_slow",      26)
    state.macd_signal     = s.get("macd_signal",    9)
    state.ema_fast        = s.get("ema_fast",       9)
    state.ema_slow        = s.get("ema_slow",       21)
    state.bb_period       = s.get("bb_period",      20)
    state.bb_std          = s.get("bb_std",          2.0)
    state.volume_ma_period= s.get("volume_ma_period", 20)
    state.leverage        = s.get("leverage",       3)
    state.cooldown_candles= s.get("cooldown_candles", 3)
    state.max_daily_loss  = s.get("max_daily_loss",  5.0)
    state.max_daily_trades= s.get("max_daily_trades", 5)
    state.trailing_enabled        = s.get("trailing_enabled", False)
    state.trailing_activation_pct = s.get("trailing_activation_pct", 0.5)
    state.trailing_distance_pct   = s.get("trailing_distance_pct", 0.3)
    state.partial_tp_enabled      = s.get("partial_tp_enabled", False)
    state.partial_tp_pct          = s.get("partial_tp_pct", 50.0)
    state.partial_tp1_pct         = s.get("partial_tp1_pct", 1.0)
    state.multi_tf_enabled        = s.get("multi_tf_enabled", False)
    state.multi_tf_list           = s.get("multi_tf_list", ["15m", "1h", "4h"])
