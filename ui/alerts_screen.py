"""
F7 Alerts — Alert log + notification channels + auto-pause config.
Mirrors the HTML design: left panel = alert log, right panel = test triggers + channels.
"""

import curses
import time

from .base import draw_box, safe_addstr, draw_btn, reg, clear_clicks, get_version, draw_header
from .colors import cg, GREEN, RED, YELLOW, CYAN, WHITE, DIM

# Alert filter options
FILTERS = ["ALL", "OK", "WARN", "ERR", "INFO"]


def _ensure_alerts(state):
    if not hasattr(state, 'alerts'):
        state.alerts = []
    if not hasattr(state, 'alert_filter'):
        state.alert_filter = "ALL"
    if not hasattr(state, 'telegram_enabled'):
        state.telegram_enabled = False
    if not hasattr(state, 'email_enabled'):
        state.email_enabled = False
    if not hasattr(state, 'autopause_daily_loss'):
        state.autopause_daily_loss = True
    if not hasattr(state, 'autopause_consec_loss'):
        state.autopause_consec_loss = False
    if not hasattr(state, 'autopause_winrate'):
        state.autopause_winrate = False


def push_alert(state, level: str, msg: str):
    """Push a new alert. Call this from anywhere in the bot."""
    _ensure_alerts(state)
    ts = time.strftime("%H:%M:%S")
    state.alerts.append({"time": ts, "level": level, "msg": msg})
    if len(state.alerts) > 200:
        state.alerts = state.alerts[-200:]


def draw_alerts(win, state):
    _ensure_alerts(state)
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()

    draw_header(win, max_x, "ALERTS", state)

    y0   = 3
    half = max_x // 2

    # ── Left: Alert Log ───────────────────────────────────────────────────────
    lh = max_y - y0 - 4
    draw_box(win, y0, 0, lh, half, "ALERT LOG", CYAN)

    # Filter bar
    fx = 2
    safe_addstr(win, y0 + 1, fx, "Filter:", cg(WHITE))
    fx += 8
    for f in FILTERS:
        is_sel = (state.alert_filter == f)
        attr   = (cg(GREEN) | curses.A_BOLD | curses.A_REVERSE) if is_sel else cg(DIM)
        lbl    = f" {f} "
        safe_addstr(win, y0 + 1, fx, lbl, attr)
        reg(y0 + 1, fx, fx + len(lbl) - 1, f"ALERT_FILTER_{f}")
        fx += len(lbl) + 1

    # Clear button
    clr_lbl = " ✖ Clear "
    safe_addstr(win, y0 + 1, half - len(clr_lbl) - 2, clr_lbl, cg(RED))
    reg(y0 + 1, half - len(clr_lbl) - 2, half - 3, "ALERT_CLEAR")

    # Alert rows
    alerts = getattr(state, 'alerts', [])
    af     = state.alert_filter
    if af != "ALL":
        shown = [a for a in alerts if a["level"] == af]
    else:
        shown = alerts

    list_y = y0 + 2
    list_h = lh - 3
    # Show newest first
    visible = list(reversed(shown))[:list_h]
    if not visible:
        safe_addstr(win, list_y + list_h // 2, 2, "No alerts.", cg(DIM))
    else:
        for i, a in enumerate(visible):
            if list_y + i >= y0 + lh - 1:
                break
            lvl = a["level"]
            col = (GREEN if lvl == "OK" else
                   YELLOW if lvl == "WARN" else
                   RED    if lvl == "ERR" else
                   CYAN)
            bar = ("┃" if lvl == "OK"   else
                   "┃" if lvl == "WARN" else
                   "┃" if lvl == "ERR"  else
                   "┃")
            safe_addstr(win, list_y + i, 1, bar, cg(col) | curses.A_BOLD)
            safe_addstr(win, list_y + i, 2, f" {a['time']} ", cg(DIM))
            safe_addstr(win, list_y + i, 12, f"{lvl:<5}", cg(col) | curses.A_BOLD)
            msg_w = half - 18
            safe_addstr(win, list_y + i, 18, a["msg"][:msg_w], cg(WHITE))

    n_total = len(alerts)
    safe_addstr(win, y0 + lh - 1, 2, f"{n_total} alerts total", cg(DIM))

    # ── Right: Test Triggers + Channels ───────────────────────────────────────
    rw = max_x - half

    # Top right: test triggers
    tr_h = 10
    draw_box(win, y0, half, tr_h, rw, "TEST TRIGGER  ·  kiểm tra pipeline", GREEN)
    safe_addstr(win, y0 + 1, half + 2, "Tạo thông báo test · kiểm tra pipeline", cg(DIM))

    test_btns = [
        (" ✔ Fake TRADE OK ", "ALERT_TEST_OK",   GREEN),
        (" ⚠ Fake WARN     ", "ALERT_TEST_WARN", YELLOW),
        (" ✖ Fake ERROR    ", "ALERT_TEST_ERR",  RED),
        (" ℹ Fake INFO     ", "ALERT_TEST_INFO", CYAN),
    ]
    for i, (lbl, act, col) in enumerate(test_btns):
        by2 = y0 + 2 + i
        safe_addstr(win, by2, half + 2, lbl, cg(col) | curses.A_BOLD)
        reg(by2, half + 2, half + 2 + len(lbl) - 1, act)

    # Channels
    ch_y = y0 + tr_h
    ch_h = 7
    draw_box(win, ch_y, half, ch_h, rw, "NOTIFICATION CHANNELS", CYAN)

    tg_on  = getattr(state, 'telegram_enabled', False)
    em_on  = getattr(state, 'email_enabled', False)

    tg_col = GREEN if tg_on else DIM
    em_col = GREEN if em_on else DIM
    tg_lbl = "[ON] " if tg_on else "[OFF]"
    em_lbl = "[ON] " if em_on else "[OFF]"

    safe_addstr(win, ch_y + 1, half + 2, f"{tg_lbl} 📨 Telegram", cg(tg_col) | curses.A_BOLD)
    reg(ch_y + 1, half + 2, half + 2 + len(tg_lbl) + 14, "ALERT_TG_TOGGLE")

    safe_addstr(win, ch_y + 2, half + 2, f"{em_lbl} ✉  Email   ", cg(em_col) | curses.A_BOLD)
    reg(ch_y + 2, half + 2, half + 2 + len(em_lbl) + 12, "ALERT_EM_TOGGLE")

    safe_addstr(win, ch_y + 3, half + 2, "Click to toggle ON/OFF", cg(DIM))

    # Auto-pause
    ap_y = ch_y + ch_h
    ap_h = max_y - ap_y - 4
    if ap_h >= 4:
        draw_box(win, ap_y, half, ap_h, rw, "AUTO-PAUSE ★", YELLOW)
        pauses = [
            ("autopause_daily_loss",  "⏸ Pause nếu Daily PnL < -5%"),
            ("autopause_consec_loss", "⏸ Pause sau N lệnh thua liên tiếp"),
            ("autopause_winrate",     "⏸ Pause nếu Win Rate < 40%"),
        ]
        for i, (attr_name, label) in enumerate(pauses):
            if ap_y + 1 + i >= ap_y + ap_h - 1:
                break
            is_on = getattr(state, attr_name, False)
            col   = GREEN if is_on else DIM
            tick  = "✔" if is_on else "○"
            safe_addstr(win, ap_y + 1 + i, half + 2, f" {tick} {label}", cg(col))
            reg(ap_y + 1 + i, half + 2, max_x - 2, f"AUTOPAUSE_{attr_name.upper()}")

    # Bottom bar
    qy = max_y - 3
    try:
        win.attron(cg(GREEN))
        win.addstr(qy - 1, 0, "─" * max_x)
        win.attroff(cg(GREEN))
    except curses.error:
        pass
    bx = 2
    w = draw_btn(win, qy, bx, "☰ Menu",    "MENU",      color=GREEN); bx += w + 1
    w = draw_btn(win, qy, bx, "◀ Back",    "BACK",      color=WHITE); bx += w + 1
    w = draw_btn(win, qy, bx, "✖ Clear",   "ALERT_CLEAR", color=RED); bx += w + 1
    safe_addstr(win, qy + 1, 2,
        "F1-F7 tabs  |  C=Clear  B=Back  Q=Quit",
        cg(DIM))

    win.refresh()
