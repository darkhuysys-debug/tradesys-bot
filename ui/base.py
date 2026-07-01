import curses
import os
from .colors import cg, GREEN, WHITE, CYAN, YELLOW, RED, DIM, BTN_BG, BTN_RED

def get_version():
    try:
        vfile = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")
        with open(vfile, "r") as f:
            return f.read().strip()
    except Exception:
        return "dev"

_click_regions = []

def clear_clicks():
    global _click_regions
    _click_regions = []

def reg(y, x1, x2, action):
    _click_regions.append((y, x1, x2, action))

def get_action_at(y, x):
    for (ry, rx1, rx2, action) in _click_regions:
        if ry == y and rx1 <= x <= rx2:
            return action
    return None

def get_region_for_action(action):
    for (ry, rx1, rx2, a) in reversed(_click_regions):
        if a == action:
            return (ry, rx1, rx2)
    return None

def draw_box(win, y, x, h, w, title="", color=None):
    attr = cg(color) if color else cg(GREEN)
    try:
        win.attron(attr)
        win.addch(y, x, curses.ACS_ULCORNER)
        win.addch(y, x + w - 1, curses.ACS_URCORNER)
        win.addch(y + h - 1, x, curses.ACS_LLCORNER)
        win.addch(y + h - 1, x + w - 1, curses.ACS_LRCORNER)
        for i in range(1, w - 1):
            win.addch(y, x + i, curses.ACS_HLINE)
            win.addch(y + h - 1, x + i, curses.ACS_HLINE)
        for i in range(1, h - 1):
            win.addch(y + i, x, curses.ACS_VLINE)
            win.addch(y + i, x + w - 1, curses.ACS_VLINE)
        win.attroff(attr)
        if title:
            label = f" {title} "
            tx = x + (w - len(label)) // 2
            win.attron(attr | curses.A_BOLD)
            win.addstr(y, tx, label)
            win.attroff(attr | curses.A_BOLD)
    except curses.error:
        pass

def safe_addstr(win, y, x, text, attr=0):
    try:
        win.addstr(y, x, str(text), attr)
    except curses.error:
        pass

def draw_btn(win, y, x, label, action, color=GREEN, highlight=False, pending=False):
    text = f" [ {label} ] "
    if pending:
        attr    = cg(YELLOW) | curses.A_BOLD | curses.A_REVERSE
        bg_attr = attr
    else:
        attr = cg(color) | curses.A_BOLD
        if color == RED:
            bg_attr = cg(BTN_RED) | curses.A_BOLD
        else:
            bg_attr = cg(BTN_BG) | curses.A_BOLD
    if highlight and not pending:
        attr |= curses.A_REVERSE
        bg_attr |= curses.A_REVERSE
    if pending or color in (RED, YELLOW):
        safe_addstr(win, y, x, text, attr)
    else:
        safe_addstr(win, y, x, text, bg_attr)
    reg(y, x, x + len(text) - 1, action)
    return len(text)

def draw_big_btn(win, y, x, label, action, color=GREEN, active=False):
    text = f" [ {label} ] "
    attr = cg(color) | curses.A_BOLD
    if active:
        attr |= curses.A_REVERSE
    safe_addstr(win, y, x, text, attr)
    reg(y, x, x + len(text) - 1, action)
    return len(text)

def draw_signal_badge(win, y, x, signal, score):
    if signal == "BUY":
        col = GREEN
        label = "BUY"
    elif signal == "SELL":
        col = RED
        label = "SELL"
    else:
        col = DIM
        label = "─"
    bw = len(label) + 2
    safe_addstr(win, y,   x,     "┌" + "─" * bw + "┐", cg(col))
    safe_addstr(win, y+1, x,     "│ " + label + " │", cg(col) | curses.A_BOLD)
    safe_addstr(win, y+2, x,     "└" + "─" * bw + "┘", cg(col))
    safe_addstr(win, y+1, x+bw+2, f"SCORE: {score}", cg(col) | curses.A_BOLD)
    safe_addstr(win, y+2, x+bw+2, f"       ", cg(col))

def draw_signal_badge_box(win, y, x, signal, score):
    if signal == "BUY":
        col = GREEN
        arrow = "▲"
    elif signal == "SELL":
        col = RED
        arrow = "▼"
    else:
        col = YELLOW
        arrow = "■"
    txt = f" {arrow} {signal} "
    bw = len(txt) + 2
    safe_addstr(win, y,   x, "┌" + "─" * bw + "┐", cg(col))
    safe_addstr(win, y+1, x, "│" + txt + "│", cg(col) | curses.A_BOLD)
    safe_addstr(win, y+2, x, "└" + "─" * bw + "┘", cg(col))
    safe_addstr(win, y+1, x+bw+2, f"SCORE: {score}", cg(col) | curses.A_BOLD)
    return bw + 3

def draw_sort_pill(win, y, x, label, active, action):
    if active:
        attr = cg(GREEN) | curses.A_BOLD | curses.A_REVERSE
        text = f"[{label}]"
    else:
        attr = cg(WHITE)
        text = f" {label} "
    safe_addstr(win, y, x, text, attr)
    reg(y, x, x + len(text) - 1, action)
    return len(text)

def flash_region(win, y, x1, x2, duration_ms=90):
    try:
        win.chgat(y, x1, x2 - x1 + 1, curses.A_REVERSE)
        win.refresh()
        curses.napms(duration_ms)
    except curses.error:
        pass

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

def spinner_char():
    import time as _time
    idx = int(_time.time() * 8) % len(_SPINNER_FRAMES)
    return _SPINNER_FRAMES[idx]

def step_toward(current, target, max_step):
    diff = target - current
    if abs(diff) <= max_step:
        return target
    return current + (max_step if diff > 0 else -max_step)

def heartbeat_on(period_s=2.5, on_fraction=0.25):
    import time as _time
    phase = (_time.time() % period_s) / period_s
    return phase < on_fraction

THEME_LABELS = [
    ('green', '● Green Matrix'),
    ('amber', '● Amber Vintage'),
    ('cyan',  '● Cyan Neon'),
    ('mono',  '● Minimal Mono'),
]

def draw_theme_bar(win, max_y, max_x):
    from .colors import cg, GREEN, DIM, CYAN, WHITE, get_theme
    y = max_y - 2
    try:
        win.attron(cg(DIM))
        win.addstr(y, 0, "─" * max_x)
        win.attroff(cg(DIM))
    except Exception:
        pass
    safe_addstr(win, y, 1, "THEME:", cg(DIM))
    x = 8
    cur = get_theme()
    for key, label in THEME_LABELS:
        is_sel = (key == cur)
        attr = cg(GREEN) | curses.A_BOLD if is_sel else cg(DIM)
        txt = f" [{label}] " if is_sel else f" {label} "
        safe_addstr(win, y, x, txt, attr)
        reg(y, x, x + len(txt) - 1, f"THEME_{key.upper()}")
        x += len(txt) + 1

TABS = [
    ("F1 Dash",   "DASHBOARD"),
    ("F2 Run",    "RUNNING"),
    ("F3 Strat",  "STRATEGY"),
    ("F4 Logs",   "LOGS"),
    ("F5 Mode",   "MODE_SELECT"),
    ("F6 Sym",    "SYMBOLS"),
    ("F7 Alert",  "ALERTS"),
    ("F8 Update", "UPDATE"),
]

def draw_header(win, max_x, active_tab, state):
    import time as _t
    mode_tag = "DEMO" if state.mode == "demo" else "REAL"
    mode_col = GREEN if state.mode == "demo" else CYAN
    pos_tag  = "1W" if getattr(state, 'position_mode', 'one-way') == "one-way" else "HEDGE"
    pos_full = "ONE-WAY" if pos_tag == "1W" else "HEDGE"
    ts       = _t.strftime("%H:%M:%S")
    n_alerts = len(getattr(state, 'alerts', []))
    alert_tag = f" 🔔{n_alerts}" if n_alerts > 0 else ""

    try:
        win.attron(cg(GREEN))
        win.addstr(0, 0, "─" * max_x)
        win.attroff(cg(GREEN))
    except curses.error:
        pass

    menu_lbl = " ☰ Menu "
    safe_addstr(win, 0, 1, menu_lbl, cg(DIM))
    reg(0, 1, 1 + len(menu_lbl) - 1, "MENU")

    brand = f" Trade SyS {get_version()} "
    bx = 1 + len(menu_lbl)
    safe_addstr(win, 0, bx, brand, cg(GREEN) | curses.A_BOLD)
    bx += len(brand)
    safe_addstr(win, 0, bx, f"[{mode_tag}]", cg(mode_col) | curses.A_BOLD)
    bx += len(mode_tag) + 3
    safe_addstr(win, 0, bx, f"[{pos_full}]", cg(YELLOW) | curses.A_BOLD)
    bx += len(pos_full) + 3
    sep = " │ "
    safe_addstr(win, 0, bx, sep, cg(DIM))
    bx += len(sep)
    ctx = f"{state.pair} · {state.timeframe} · {state.leverage}x"
    safe_addstr(win, 0, bx, ctx, cg(CYAN))
    bx += len(ctx)
    safe_addstr(win, 0, bx, sep, cg(DIM))
    bx += len(sep)
    al_lbl = f"🔔 {n_alerts} alert{'s' if n_alerts != 1 else ''}"
    safe_addstr(win, 0, bx, al_lbl, cg(YELLOW if n_alerts > 0 else DIM))
    clk = _t.strftime("%H:%M:%S")
    safe_addstr(win, 0, max(0, max_x - len(clk) - 2), clk, cg(DIM))

    tx = 2
    for label, action in TABS:
        is_active = (action == active_tab)
        attr = (cg(CYAN) | curses.A_BOLD | curses.A_UNDERLINE) if is_active else cg(WHITE)
        text = f" {label} "
        safe_addstr(win, 1, tx, text, attr)
        reg(1, tx, tx + len(text) - 1, action)
        tx += len(text) + 1

    try:
        win.attron(cg(GREEN))
        win.addstr(2, 0, "─" * max_x)
        win.attroff(cg(GREEN))
    except curses.error:
        pass
