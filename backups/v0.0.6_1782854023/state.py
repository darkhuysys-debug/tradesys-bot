import threading
import time
from typing import List, Optional

class BotState:
    def __init__(self):
        self._lock = threading.Lock()
        # Mode: "demo" or "real"
        self.mode = "demo"
        # Bybit credentials (real mode)
        self.bybit_api_key      = ""
        self.bybit_api_secret   = ""
        self.bybit_connected    = False
        self.telegram_bot_token = ""
        self.telegram_chat_id   = ""
        self.bybit_error      = ""
        # Bot
        self.status       = "STOPPED"
        self.pid          = 0
        self.started      = ""
        self.start_time: Optional[float] = None
        self.strategy     = "RSI + MACD"
        self.risk_mode    = "MEDIUM"
        # PNL
        self.pnl_usdt     = 0.0
        self.pnl_pct      = 0.0
        self.pnl_history: List[float] = []
        self.pnl_today    = 0.0
        # Accounts
        self.accounts: List[dict] = []
        # Positions / trades
        self.positions: List[dict]     = []
        self.recent_trades: List[dict] = []
        # Logs
        self.logs: List[str] = []
        # Market
        self.market_price     = 0.0
        self.market_change_24h = 0.0
        self.market_high_24h  = 0.0
        self.market_low_24h   = 0.0
        self.market_volume    = 0.0
        self.equity           = 0.0
        # Strategy params
        self.max_positions    = 3
        self.rsi_period       = 14
        self.rsi_oversold     = 30
        self.rsi_overbought   = 70
        self.macd_fast        = 12
        self.macd_slow        = 26
        self.macd_signal      = 9
        self.risk_per_trade   = 1.0
        self.take_profit      = 2.0
        self.stop_loss        = 1.0
        self.timeframe        = "15m"
        self.pair             = "BTC/USDT"
        self.ema_fast         = 9
        self.ema_slow         = 21
        self.bb_period        = 20
        self.bb_std           = 2.0
        self.volume_ma_period = 20
        # F8 Update screen mode
        self.f8_mode = "update"
        self.f8_file_rows = []
        self.f8_file_scroll = 0
        self.f8_file_sel = 0
        self.leverage         = 3
        self.cooldown_candles = 3
        self.max_daily_loss   = 5.0
        self.max_daily_trades = 5
        self.position_mode    = "one-way"
        # Signal state
        self.current_rsi      = 0.0
        self.current_macd     = ""
        self.signal           = "NONE"
        self.score            = 0
        self.macd_histogram   = 0.0
        self.current_ema_fast = 0.0
        self.current_ema_slow = 0.0
        self.bb_upper         = 0.0
        self.bb_middle        = 0.0
        self.bb_lower         = 0.0
        self.signal_reasons   = []
        self.rsi_history      = []
        # Risk state
        self.daily_trades     = 0
        self.daily_pnl        = 0.0
        self.cooldown_until   = 0.0
        self.consecutive_losses = 0
        self.max_consecutive_losses = 3
        # Trade guard
        self.last_trade_signal = "NONE"
        self.last_trade_time   = 0.0
        self.trade_cooldown_until = 0.0
        # Thread control
        self.bot_thread: Optional[threading.Thread] = None
        self.running = False
        self._stop_event: Optional[threading.Event] = None
        # Auto-pause flags
        self.autopause_daily_loss  = True
        self.autopause_consec_loss = False
        self.autopause_winrate     = False
        # Trailing stop
        self.trailing_enabled        = False
        self.trailing_activation_pct = 0.5
        self.trailing_distance_pct   = 0.3
        self._trailing_active: dict  = {}
        # Partial TP
        self.partial_tp_enabled  = False
        self.partial_tp_pct      = 50.0
        self.partial_tp1_pct     = 1.0
        # Multi-TF
        self.multi_tf_enabled     = False
        self.multi_tf_list        = ["15m", "1h", "4h"]
        self.tf_signals: dict     = {}
        self.tf_consensus         = ""
        self.tf_consensus_score   = 0
        # Market Regime
        self.regime              = ""
        self.regime_strength     = 0.0
        self.regime_adx          = 0.0
        self.regime_atr_pct      = 0.0
        # Alerts
        self.alerts: list        = []
        self.alert_filter: str   = "ALL"
        self.telegram_enabled    = False
        self.email_enabled       = False
        # UI-only transient state (not persisted, not trading-related)
        self.pending_confirm_action: Optional[str] = None
        self.pending_confirm_until: float = 0.0
        self.equity_display: float = 0.0   # animates toward self.equity
        self.pnl_display: float = 0.0      # animates toward self.pnl_usdt
        # Symbol watchlist (managed by F6 Symbols tab)
        self.watchlist_order: list = []          # ordered list of symbol strings
        self.active_symbols: set  = set()        # symbols marked active (shown in watchlist)
        self.watchlist: list      = []           # list of dicts with live market data

    def add_log(self, msg: str, level: str = "INFO"):
        with self._lock:
            ts   = time.strftime("%H:%M:%S")
            line = f"[{ts}] [{level}] {msg}"
            self.logs.append(line)
            if len(self.logs) > 1000:
                self.logs = self.logs[-1000:]

    def get_uptime_str(self) -> str:
        if not self.start_time:
            return "00:00:00"
        secs = int(time.time() - self.start_time)
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def get_main_account(self) -> Optional[dict]:
        for a in self.accounts:
            if a.get("connected"):
                return a
        return None

state = BotState()

# (appended by update) Symbol watchlist fields
# These are initialised by the symbols_screen on first use so we keep them
# as None here to avoid import-order issues.
