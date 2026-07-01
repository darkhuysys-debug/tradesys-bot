import curses
import time
from .base import draw_box, safe_addstr, draw_btn, reg, clear_clicks, get_version, draw_header
from .colors import cg, GREEN, WHITE, CYAN, YELLOW, RED, DIM

CORE_FIELDS = [
    ("pair",              "Trading Pair",       str),
    ("timeframe",         "Timeframe",          str),
    ("leverage",          "Leverage",           int),
    ("risk_per_trade",    "Risk / Trade (%)",   float),
    ("take_profit",       "Take Profit (%)",    float),
    ("stop_loss",         "Stop Loss (%)",      float),
    ("max_positions",     "Max Positions",      int),
]

INDICATOR_FIELDS = [
    ("rsi_period",        "RSI Period",         int),
    ("rsi_oversold",      "RSI Oversold",       int),
    ("rsi_overbought",    "RSI Overbought",     int),
    ("macd_fast",         "MACD Fast",          int),
    ("macd_slow",         "MACD Slow",          int),
    ("macd_signal",       "MACD Signal",        int),
    ("ema_fast",          "EMA Fast",           int),
    ("ema_slow",          "EMA Slow",           int),
    ("bb_period",         "BB Period",          int),
    ("bb_std",            "BB Std Dev",         float),
    ("volume_ma_period",  "Vol MA Period",      int),
]

RISK_FIELDS = [
    ("max_daily_loss",         "Max Daily Loss (%)", float),
    ("max_daily_trades",       "Max Daily Trades",   int),
    ("cooldown_candles",       "Cooldown Candles",   int),
    ("max_consecutive_losses", "Max Consec.Losses",  int),
]

FIELDS = CORE_FIELDS + INDICATOR_FIELDS + RISK_FIELDS

AUTOPAUSE_ITEMS = [
    ("autopause_daily_loss",  "\u23f8 Pause n\u1ebfu Daily PnL < -5%"),
    ("autopause_consec_loss", "\u23f8 Pause sau N l\u1ec7nh thua li\u00ean ti\u1ebfp"),
    ("autopause_winrate",     "\u23f8 Pause n\u1ebfu Win Rate < 40%"),
]

def _field_color(key, val):
    if key == "take_profit":   return GREEN
    if key == "stop_loss":     return RED
    if key == "max_daily_loss": return RED
    if key == "max_consecutive_losses": return YELLOW
    return CYAN

def draw_strategy(win, state, selected=0, editing=False, edit_buf=""):
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()

    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from state import state as _st
    draw_header(win, max_x, "STRATEGY", _st)

    y0 = 3

    per_col = max_x // 3
    col3_w  = max_x - 2 * per_col
    ch      = max_y - y0 - 4

    draw_box(win, y0, 0, ch, per_col, "CORE SETTINGS", GREEN)
    for i, (key, label, typ) in enumerate(CORE_FIELDS):
        row = y0 + 2 + i
        if row >= y0 + ch - 1:
            break
        idx      = i
        raw_val  = getattr(_st, key, "")
        hl       = curses.A_REVERSE if selected == idx else 0
        disp     = edit_buf if (editing and selected == idx) else str(raw_val)
        col      = _field_color(key, raw_val)

        lbl_w = per_col // 2 - 1
        safe_addstr(win, row, 2, f"{label}:"[:lbl_w], cg(WHITE))
        vx   = lbl_w + 3
        vw   = per_col - vx - 2
        safe_addstr(win, row, vx, f"{disp[:vw]:<{vw}}", cg(col) | hl)
        reg(row, vx, vx + vw - 1, f"FIELD_{idx}")

    x1 = per_col
    draw_box(win, y0, x1, ch, per_col, "INDICATORS", GREEN)
    for i, (key, label, typ) in enumerate(INDICATOR_FIELDS):
        row = y0 + 2 + i
        if row >= y0 + ch - 1:
            break
        idx      = len(CORE_FIELDS) + i
        raw_val  = getattr(_st, key, "")
        hl       = curses.A_REVERSE if selected == idx else 0
        disp     = edit_buf if (editing and selected == idx) else str(raw_val)
        col      = _field_color(key, raw_val)

        lbl_w = per_col // 2 - 1
        safe_addstr(win, row, x1 + 2, f"{label}:"[:lbl_w], cg(WHITE))
        vx   = x1 + lbl_w + 3
        vw   = per_col - lbl_w - 6
        safe_addstr(win, row, vx, f"{disp[:vw]:<{vw}}", cg(col) | hl)
        reg(row, vx, vx + vw - 1, f"FIELD_{idx}")

    x2 = 2 * per_col
    draw_box(win, y0, x2, ch, col3_w, "RISK LIMITS", GREEN)

    risk_base = len(CORE_FIELDS) + len(INDICATOR_FIELDS)
    for i, (key, label, typ) in enumerate(RISK_FIELDS):
        row = y0 + 2 + i
        if row >= y0 + ch - 1:
            break
        idx     = risk_base + i
        raw_val = getattr(_st, key, "")
        hl      = curses.A_REVERSE if selected == idx else 0
        disp    = edit_buf if (editing and selected == idx) else str(raw_val)
        col     = _field_color(key, raw_val)

        lbl_w = col3_w // 2 - 1
        safe_addstr(win, row, x2 + 2, f"{label}:"[:lbl_w], cg(WHITE))
        vx  = x2 + lbl_w + 3
        vw  = col3_w - lbl_w - 6
        safe_addstr(win, row, vx, f"{disp[:vw]:<{vw}}", cg(col) | hl)
        reg(row, vx, vx + vw - 1, f"FIELD_{idx}")

    ap_y = y0 + 2 + len(RISK_FIELDS) + 1
    if ap_y < y0 + ch - 1:
        safe_addstr(win, ap_y, x2 + 2, "AUTO-PAUSE \u2605", cg(YELLOW) | curses.A_BOLD)
        for j, (attr, label) in enumerate(AUTOPAUSE_ITEMS):
            row = ap_y + 1 + j
            if row >= y0 + ch - 1:
                break
            is_on = getattr(_st, attr, False)
            col   = GREEN if is_on else DIM
            mark  = "\u25a0" if is_on else "\u25a1"
            bar_w = col3_w - 5
            txt   = f" {mark} {label} "
            safe_addstr(win, row, x2 + 2, txt[:bar_w-3], cg(col) | (curses.A_BOLD if is_on else 0))
            reg(row, x2 + 2, x2 + col3_w - 3, f"AUTOPAUSE_{attr.upper()}")

    btn_row = y0 + ch - 2
    if btn_row > ap_y + len(AUTOPAUSE_ITEMS) + 1 and btn_row < max_y - 2:
        bx = x2 + 2
        w = draw_btn(win, btn_row, bx, "\U0001f4be Save Config", "STRAT_SAVE"); bx += w + 1
        w = draw_btn(win, btn_row, bx, "\u21ba Reset",           "STRAT_RESET"); bx += w + 1
        draw_btn(win, btn_row, bx, "\u25b6 Start", "START", color=GREEN)

    live_y = max_y - 3
    rsi_v  = getattr(_st, 'current_rsi', 0.0)
    macd_h = getattr(_st, 'macd_histogram', 0.0)
    ema_f  = getattr(_st, 'current_ema_fast', 0.0)
    ema_s  = getattr(_st, 'current_ema_slow', 0.0)
    price  = getattr(_st, 'market_price', 0.0)
    sig    = getattr(_st, 'signal', 'NONE')
    score  = getattr(_st, 'score', 0)
    sig_lbl = "\u25b2 BUY" if sig == "BUY" else "\u25bc SELL" if sig == "SELL" else "\u25a0 NONE"
    sig_col = GREEN if sig == "BUY" else RED if sig == "SELL" else DIM
    live_parts = [
        (" LIVE ", cg(GREEN) | curses.A_BOLD | curses.A_REVERSE),
        (f"  RSI {rsi_v:.1f}  |  MACD hist {macd_h:+.2f}  |  EMA {ema_f:.0f}/{ema_s:.0f}  |  Signal: ", cg(CYAN)),
        (f"{sig_lbl} ({score})", cg(sig_col) | curses.A_BOLD),
        (f"  |  Price: {price:,.1f}", cg(CYAN)),
    ]
    cx = 0
    for txt, attr in live_parts:
        if cx + len(txt) < max_x - 1:
            safe_addstr(win, live_y, cx, txt, attr)
            cx += len(txt)

    hint_y = max_y - 2
    if editing:
        safe_addstr(win, hint_y, 0, " Editing — Enter: save  |  Esc: cancel ", cg(YELLOW))
    else:
        safe_addstr(win, hint_y, 0,
            " Click field to edit  |  ↑↓ navigate  |  Enter to edit  |  S=Save  R=Reset  B=Back",
            cg(GREEN))

    
    from .base import draw_theme_bar
    draw_theme_bar(win, max_y, max_x)
    win.refresh()
