"""Mode selection screen (Demo / Real / Position Mode) and API key input."""
import curses
import time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from state import state
from .base import draw_box, safe_addstr, draw_btn, reg, clear_clicks, get_version, spinner_char, draw_header
from .colors import cg, GREEN, RED, YELLOW, CYAN, WHITE, DIM

def draw_mode_select(win, current_mode="demo", pos_mode="one-way"):
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()
    draw_header(win, max_x, "MODE_SELECT", __import__('sys').modules['state'].state)

    y0 = 3

    t1 = "─── TRADING MODE ───"
    safe_addstr(win, y0, (max_x - len(t1)) // 2, t1, cg(GREEN) | curses.A_BOLD)

    cw, ch = max_x // 2 - 3, 8
    dx, rx = 2, max_x // 2 + 1
    dy = y0 + 1

    hl_demo = current_mode == "demo"
    hl_real = current_mode == "real"

    draw_box(win, dy, dx, ch, cw, "[ D ]  DEMO MODE" + ("  ✔" if hl_demo else ""), GREEN if hl_demo else WHITE)
    for i, line in enumerate([
        "  Bybit demo account",
        "  Live market data",
        "  No real money risk",
        "  Requires demo API key",
        "",
        "  Press [D] or click",
    ]):
        attr = cg(GREEN) | curses.A_BOLD if hl_demo else cg(WHITE)
        safe_addstr(win, dy+1+i, dx+1, line[:cw-2], attr)
    for row in range(dy, dy+ch):
        reg(row, dx, dx+cw-1, "MODE_DEMO")

    draw_box(win, dy, rx, ch, cw, "[ R ]  REAL MODE" + ("  ✔" if hl_real else ""), CYAN if hl_real else WHITE)
    for i, line in enumerate([
        "  Bybit mainnet",
        "  Real orders — real money",
        "  Live market data",
        "  ⚠  Financial risk",
        "",
        "  Press [R] or click",
    ]):
        attr = cg(CYAN) | curses.A_BOLD if hl_real else cg(WHITE)
        safe_addstr(win, dy+1+i, rx+1, line[:cw-2], attr)
    for row in range(dy, dy+ch):
        reg(row, rx, rx+cw-1, "MODE_REAL")

    pm_y = dy + ch + 1
    t2   = "─── POSITION MODE ───"
    safe_addstr(win, pm_y, (max_x - len(t2)) // 2, t2, cg(YELLOW) | curses.A_BOLD)

    pw, ph = max_x // 2 - 3, 7
    ox, hx = 2, max_x // 2 + 1
    oy = pm_y + 1

    hl_ow = pos_mode == "one-way"
    hl_hg = pos_mode == "hedge"

    draw_box(win, oy, ox, ph, pw, "[ 1 ]  ONE-WAY" + ("  ✔" if hl_ow else ""), GREEN if hl_ow else WHITE)
    for i, line in enumerate([
        "  LONG or SHORT only",
        "  Cannot hold both directions",
        "  Standard account",
        "",
        "  Press [1] to select",
    ]):
        attr = cg(GREEN) | curses.A_BOLD if hl_ow else cg(WHITE)
        safe_addstr(win, oy+1+i, ox+1, line[:pw-2], attr)
    for row in range(oy, oy+ph):
        reg(row, ox, ox+pw-1, "POS_ONE_WAY")

    draw_box(win, oy, hx, ph, pw, "[ 2 ]  HEDGE" + ("  ✔" if hl_hg else ""), CYAN if hl_hg else WHITE)
    for i, line in enumerate([
        "  LONG + SHORT simultaneously",
        "  positionIdx = 0 / 1",
        "  Enable Hedge Mode on Bybit first",
        "",
        "  Press [2] to select",
    ]):
        attr = cg(CYAN) | curses.A_BOLD if hl_hg else cg(WHITE)
        safe_addstr(win, oy+1+i, hx+1, line[:pw-2], attr)
    for row in range(oy, oy+ph):
        reg(row, hx, hx+pw-1, "POS_HEDGE")

    by = oy + ph + 1
    bx = (max_x - 36) // 2
    going_real = (current_mode == "real")
    pending = going_real and state.pending_confirm_action == "MODE_CONFIRM"
    if pending:
        w = draw_btn(win, by, bx, "⚠ Press again to confirm REAL", "MODE_CONFIRM", pending=True)
    else:
        w = draw_btn(win, by, bx, "✔ Confirm & Save", "MODE_CONFIRM", color=GREEN)
    bx += w + 2
    draw_btn(win, by, bx, "✖ Cancel", "DASHBOARD", color=RED)

    mode_col = GREEN if current_mode == "demo" else CYAN
    pm_col   = GREEN if pos_mode == "one-way" else CYAN
    sx = (max_x - 60) // 2
    safe_addstr(win, by + 1, sx, " Selected:  Bot = ", cg(WHITE))
    safe_addstr(win, by + 1, sx + 19, current_mode.upper(), cg(mode_col) | curses.A_BOLD)
    pm_x = sx + 19 + len(current_mode)
    safe_addstr(win, by + 1, pm_x, "  |  Position = ", cg(WHITE))
    safe_addstr(win, by + 1, pm_x + 16, pos_mode.upper(), cg(pm_col) | curses.A_BOLD)

    safe_addstr(win, max_y-2, 2,
        "[D] Demo  [R] Real  [1] One-way  [2] Hedge  [Enter] Confirm  [B] Back",
        cg(GREEN))
    
    from .base import draw_theme_bar
    draw_theme_bar(win, max_y, max_x)
    win.refresh()


APIFIELDS = [
    ("bybit_api_key",      "BYBIT Key    "),
    ("bybit_api_secret",   "BYBIT Secret "),
    ("okx_api_key",        "OKX Key      "),
    ("okx_api_secret",     "OKX Secret   "),
    ("telegram_bot_token", "TG Token     "),
    ("telegram_chat_id",   "TG Chat ID   "),
    ("sendgrid_api_key",   "SG API Key   "),
    ("email_from",         "From Email   "),
]

EXCHANGES = ["bybit", "okx"]
OKX_MARKETS = ["futures", "spot"]

def _ensure_api_state(state):
    if not hasattr(state, 'bybit_api_key'):
        state.bybit_api_key = ""
    if not hasattr(state, 'bybit_api_secret'):
        state.bybit_api_secret = ""
    if not hasattr(state, 'okx_api_key'):
        state.okx_api_key = ""
    if not hasattr(state, 'okx_api_secret'):
        state.okx_api_secret = ""
    if not hasattr(state, 'okx_market'):
        state.okx_market = "futures"
    if not hasattr(state, 'telegram_bot_token'):
        state.telegram_bot_token = ""
    if not hasattr(state, 'telegram_chat_id'):
        state.telegram_chat_id = ""
    if not hasattr(state, 'sendgrid_api_key'):
        state.sendgrid_api_key = ""
    if not hasattr(state, 'email_from'):
        state.email_from = "" 

def draw_api_input(win, state, selected=0, editing=False, edit_buf="",
                   status_msg="", status_ok=True, testing=False):
    _ensure_api_state(state)
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()
    draw_header(win, max_x, "MODE_SELECT", state)

    bw = min(74, max_x - 4)
    bx = (max_x - bw) // 2
    by = max(3, max_y // 2 - 9)

    draw_box(win, by, bx, 28, bw, "⚙  API & ALERT SETTINGS", CYAN)

    safe_addstr(win, by+1, bx+2,
        "Enter API Key and Secret from Bybit or OKX.",
        cg(WHITE))
    safe_addstr(win, by+2, bx+2,
        "Create at:  bybit.com → API Management  |  okx.com → API Key",
        cg(YELLOW))
    safe_addstr(win, by+3, bx+2,
        "Required permissions:  Read  +  Trade  (NO Withdraw needed)",
        cg(GREEN))

    mode_col = GREEN if state.mode == "demo" else RED
    mode_lbl = "DEMO (testnet)" if state.mode == "demo" else "REAL (mainnet)"
    safe_addstr(win, by+4, bx+2, "Current mode: ", cg(WHITE))
    safe_addstr(win, by+4, bx+16, mode_lbl, cg(mode_col) | curses.A_BOLD)

    safe_addstr(win, by+5, bx+2, "── BYBIT ──────────────────────────────────────", cg(DIM))
    safe_addstr(win, by+5+4, bx+2, "── OKX ────────────────────────────────────────", cg(DIM))
    safe_addstr(win, by+5+8, bx+2, "── TELEGRAM (optional) ────────────────────────", cg(DIM))

    for i, (key, label) in enumerate(APIFIELDS):
        row  = by + 6 + i * 2 + (1 if i >= 4 else 0)
        val  = getattr(state, key, "")
        disp = edit_buf if (editing and selected == i) else val
        if key in ("bybit_api_secret", "okx_api_secret") and not (editing and selected == i):
            disp = "●" * min(len(disp), 32) if disp else ""
        hl   = curses.A_REVERSE if selected == i else 0
        safe_addstr(win, row, bx+2, f"{label}:", cg(WHITE) | curses.A_BOLD)
        field_len = bw - 20
        field_txt = f" {disp[:field_len-2]:<{field_len-2}} "
        safe_addstr(win, row, bx+15, field_txt, cg(CYAN) | hl)
        reg(row, bx+15, bx+15+len(field_txt)-1, f"APIFIELD_{i}")
        hint_col = YELLOW if (selected == i and editing) else DIM
        hint     = "← editing" if (selected == i and editing) else "click to enter"
        safe_addstr(win, row, bx+15+len(field_txt)+1, hint, cg(hint_col))

    sr = by + 17
    if testing:
        safe_addstr(win, sr, bx+2, f"{spinner_char()} Testing connection...", cg(YELLOW) | curses.A_BOLD)
    elif status_msg:
        sc   = GREEN if status_ok else RED
        icon = "✓" if status_ok else "✗"
        safe_addstr(win, sr, bx+2, f"{icon} {status_msg}", cg(sc) | curses.A_BOLD)

    # Telegram toggle
    tg_on = getattr(state, 'telegram_enabled', False)
    tg_col = GREEN if tg_on else DIM
    tg_lbl = "[ON]" if tg_on else "[OFF]"
    safe_addstr(win, sr, bx + 30, f"{tg_lbl} 📨 Telegram", cg(tg_col) | curses.A_BOLD)
    reg(sr, bx + 30, bx + 48, "API_TG_TOGGLE")

    bb = by + 18
    bstart = bx + 2
    w = draw_btn(win, bb, bstart, "🔌 Test Connection", "API_TEST");  bstart += w + 1
    w = draw_btn(win, bb, bstart, "📨 Send Test",       "API_TG_TEST"); bstart += w + 1
    w = draw_btn(win, bb, bstart, "💾 Save & Apply",    "API_SAVE");  bstart += w + 1
    w = draw_btn(win, bb, bstart, "⚑ Change Mode",      "MODE_SELECT"); bstart += w + 1
    draw_btn(win, bb, bstart, "✖ Cancel", "DASHBOARD", color=RED)

    if editing:
        safe_addstr(win, bb+1, bx+2,
            "Editing — Enter: done  |  Esc: cancel  |  Tab: next field",
            cg(YELLOW))
    else:
        safe_addstr(win, bb+1, bx+2,
            "Click field to enter  |  ↑↓ select  |  T test  |  S save  |  B back",
            cg(GREEN))
    
    from .base import draw_theme_bar
    draw_theme_bar(win, max_y, max_x)
    win.refresh()


# ─────────────────────────────────────────────────────────────────────────────
# Combined F5 screen: Mode Select (left) + API Settings (right)
# Matches HTML layout exactly.
# ─────────────────────────────────────────────────────────────────────────────
def draw_mode_api_combined(win, current_mode, pos_mode,
                           api_sel=0, api_editing=False, api_buf="",
                           api_status="", api_status_ok=True, api_testing=False,
                           email_status="", email_status_ok=True, email_testing=False):
    """Single F5 screen: left = Trading Mode, right = API Settings."""
    _ensure_api_state(state)
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()
    draw_header(win, max_x, "MODE_SELECT", state)

    y0   = 3
    half = max_x // 2

    # ══════════════ LEFT PANEL: TRADING MODE ══════════════
    lw = half - 1

    # ── Account mode title
    safe_addstr(win, y0, 2, "ACCOUNT MODE", cg(DIM) | curses.A_BOLD)

    cw = (lw - 3) // 2
    ch = 7

    hl_demo = current_mode == "demo"
    hl_real = current_mode == "real"

    # Demo box
    demo_title = "[ D ] DEMO MODE" + (" ✔" if hl_demo else "")
    draw_box(win, y0+1, 1, ch, cw, demo_title, GREEN if hl_demo else DIM)
    demo_lines = [
        "✔ Bybit demo account",
        "✔ Live market data",
        "✔ No real money risk",
        "✔ Requires demo API key",
        "  Press [D] or click",
    ]
    for i, line in enumerate(demo_lines):
        attr = cg(GREEN) | curses.A_BOLD if hl_demo else cg(DIM)
        safe_addstr(win, y0+2+i, 3, line[:cw-3], attr)
    for row in range(y0+1, y0+1+ch):
        reg(row, 1, 1+cw-1, "MODE_DEMO")

    # Real box
    real_title = "[ R ] REAL MODE" + (" ✔" if hl_real else "")
    rx = 1 + cw + 1
    draw_box(win, y0+1, rx, ch, cw, real_title, CYAN if hl_real else DIM)
    real_lines = [
        "✔ Bybit mainnet",
        "✔ Real orders",
        "⚠ Real money risk",
        "⚠ Confirm 2x to activate",
        "  Press [R] or click",
    ]
    for i, line in enumerate(real_lines):
        attr = cg(CYAN) | curses.A_BOLD if hl_real else cg(DIM)
        safe_addstr(win, y0+2+i, rx+2, line[:cw-3], attr)
    for row in range(y0+1, y0+1+ch):
        reg(row, rx, rx+cw-1, "MODE_REAL")

    # ── Position mode title
    pm_y = y0 + 1 + ch + 1
    safe_addstr(win, pm_y, 2, "POSITION MODE", cg(DIM) | curses.A_BOLD)

    ph = 6
    hl_ow = pos_mode == "one-way"
    hl_hg = pos_mode == "hedge"

    ow_title = "[ 1 ] ONE-WAY" + (" ✔" if hl_ow else "")
    draw_box(win, pm_y+1, 1, ph, cw, ow_title, GREEN if hl_ow else DIM)
    for i, line in enumerate(["LONG or SHORT only", "Standard account", "✔ positionIdx = 0", "  Press [1]"]):
        safe_addstr(win, pm_y+2+i, 3, line[:cw-3], cg(GREEN) | curses.A_BOLD if hl_ow else cg(DIM))
    for row in range(pm_y+1, pm_y+1+ph):
        reg(row, 1, 1+cw-1, "POS_ONE_WAY")

    hg_title = "[ 2 ] HEDGE" + (" ✔" if hl_hg else "")
    draw_box(win, pm_y+1, rx, ph, cw, hg_title, CYAN if hl_hg else DIM)
    for i, line in enumerate(["LONG + SHORT same time", "positionIdx 0 / 1", "⚠ Enable on Bybit first", "  Press [2]"]):
        safe_addstr(win, pm_y+2+i, rx+2, line[:cw-3], cg(CYAN) | curses.A_BOLD if hl_hg else cg(DIM))
    for row in range(pm_y+1, pm_y+1+ph):
        reg(row, rx, rx+cw-1, "POS_HEDGE")

    # ── Confirm / Cancel buttons
    btn_y = pm_y + 1 + ph + 1
    going_real = (current_mode == "real")
    pending    = going_real and state.pending_confirm_action == "MODE_CONFIRM"
    bx2 = 2
    w = draw_btn(win, btn_y, bx2, "⚠ Press again to confirm REAL" if pending else "✔ Confirm & Save",
                 "MODE_CONFIRM", pending=pending, color=GREEN)
    bx2 += w + 2
    draw_btn(win, btn_y, bx2, "✖ Cancel", "DASHBOARD", color=RED)

    # Status line
    mode_col = GREEN if current_mode == "demo" else CYAN
    pm_col   = GREEN if pos_mode == "one-way" else CYAN
    safe_addstr(win, btn_y+1, 2, "Mode: ", cg(DIM))
    safe_addstr(win, btn_y+1, 8, current_mode.upper(), cg(mode_col) | curses.A_BOLD)
    safe_addstr(win, btn_y+1, 8+len(current_mode)+2, " | Pos: ", cg(DIM))
    safe_addstr(win, btn_y+1, 8+len(current_mode)+10, pos_mode.upper(), cg(pm_col) | curses.A_BOLD)

    # ══════════════ RIGHT PANEL: API SETTINGS ══════════════
    rw = max_x - half - 1
    rx2 = half + 1

    # ── Bybit API Key box
    draw_box(win, y0, rx2, 9, rw, "BYBIT API KEY", CYAN)
    mode_lbl = "DEMO (testnet)" if current_mode == "demo" else "REAL (mainnet)"
    mode_clr = GREEN if current_mode == "demo" else RED
    safe_addstr(win, y0+1, rx2+2, "Tạo tại: ", cg(DIM))
    safe_addstr(win, y0+1, rx2+10, "bybit.com → Account → API Management", cg(CYAN))
    safe_addstr(win, y0+2, rx2+2, "Quyền: ", cg(DIM))
    safe_addstr(win, y0+2, rx2+10, "Read + Trade  (KHÔNG cần Withdraw)", cg(GREEN))
    safe_addstr(win, y0+3, rx2+2, "Mode hiện tại: ", cg(DIM))
    safe_addstr(win, y0+3, rx2+18, mode_lbl, cg(mode_clr) | curses.A_BOLD)

    bybit_fields = [
        ("bybit_api_key",    "API Key   "),
        ("bybit_api_secret", "API Secret"),
    ]
    for i, (key, label) in enumerate(bybit_fields):
        row = y0 + 4 + i
        val = getattr(state, key, "")
        if key == "bybit_api_secret" and not (api_editing and api_sel == i):
            disp = "●" * min(len(val), 20) if val else ""
        else:
            disp = api_buf if (api_editing and api_sel == i) else val
        hl   = curses.A_REVERSE if api_sel == i else 0
        safe_addstr(win, row, rx2+2, f"{label}:", cg(WHITE) | curses.A_BOLD)
        flen = rw - 16
        safe_addstr(win, row, rx2+14, f" {disp[:flen]:<{flen}} ", cg(CYAN) | hl)
        reg(row, rx2+14, rx2+14+flen+1, f"APIFIELD_{i}")

    # API buttons
    abx = rx2 + 2
    w = draw_btn(win, y0+7, abx, "🔌 Test", "API_TEST", color=CYAN); abx += w+1
    w = draw_btn(win, y0+7, abx, "💾 Save", "API_SAVE", color=GREEN); abx += w+1

    tg_y = y0 + 9
    api_status_y = tg_y + 12
    if api_testing:
        safe_addstr(win, api_status_y, rx2+2, f"{spinner_char()} Testing Bybit API...", cg(YELLOW) | curses.A_BOLD)
    elif api_status:
        sc = GREEN if api_status_ok else RED
        safe_addstr(win, api_status_y, rx2+2, f"{'OK' if api_status_ok else 'ERR'}: {api_status[:rw-8]}", cg(sc) | curses.A_BOLD)

    email_status_y = api_status_y + 1
    if email_testing:
        safe_addstr(win, email_status_y, rx2+2, f"{spinner_char()} Testing SMTP...", cg(YELLOW) | curses.A_BOLD)
    elif email_status:
        sc = GREEN if email_status_ok else RED
        safe_addstr(win, email_status_y, rx2+2, f"{'OK' if email_status_ok else 'ERR'}: {email_status[:rw-8]}", cg(sc) | curses.A_BOLD)

    # ── Telegram Alerts box
    tg_h = max_y - tg_y - 3
    if tg_h < 5:
        tg_h = 5
    draw_box(win, tg_y, rx2, tg_h, rw, "TELEGRAM ALERTS", CYAN)

    tg_fields = [
        ("telegram_bot_token", "Bot Token "),
        ("telegram_chat_id",   "Chat ID   "),
    ]
    for i, (key, label) in enumerate(tg_fields):
        fi = i + 2  # api_sel index offset
        row = tg_y + 1 + i
        val = getattr(state, key, "")
        disp = api_buf if (api_editing and api_sel == fi) else val
        hl   = curses.A_REVERSE if api_sel == fi else 0
        safe_addstr(win, row, rx2+2, f"{label}:", cg(WHITE) | curses.A_BOLD)
        flen = rw - 16
        safe_addstr(win, row, rx2+14, f" {disp[:flen]:<{flen}} ", cg(CYAN) | hl)
        reg(row, rx2+14, rx2+14+flen+1, f"APIFIELD_{fi}")

    tg_on  = getattr(state, 'telegram_enabled', False)
    tg_col = GREEN if tg_on else DIM
    tg_lbl = "[ ON ]" if tg_on else "[OFF ]"
    safe_addstr(win, tg_y+3, rx2+2, f"{tg_lbl} 📨 Telegram", cg(tg_col) | curses.A_BOLD)
    reg(tg_y+3, rx2+2, rx2+20, "API_TG_TOGGLE")

    em_on  = getattr(state, 'email_enabled', False)
    em_col = GREEN if em_on else DIM
    em_lbl = "[ ON ]" if em_on else "[OFF ]"

    sg_fields = [
        ("sendgrid_api_key", "SG API Key "),
        ("email_from",       "From Email "),
    ]
    for i, (key, label) in enumerate(sg_fields):
        fi = i + 4
        erow = tg_y + 6 + i
        val  = getattr(state, key, "")
        disp = api_buf if (api_editing and api_sel == fi) else val
        if key == "sendgrid_api_key" and not (api_editing and api_sel == fi):
            disp = "●" * min(len(disp), 20) if disp else ""
        hl   = curses.A_REVERSE if api_sel == fi else 0
        safe_addstr(win, erow, rx2+2, f"{label}:", cg(WHITE) | curses.A_BOLD)
        flen = rw - 20
        safe_addstr(win, erow, rx2+16, f" {disp[:flen]:<{flen}} ", cg(CYAN) | hl)
        reg(erow, rx2+16, rx2+16+flen+1, f"APIFIELD_{fi}")

    em_toggle_row = tg_y + 5
    safe_addstr(win, em_toggle_row, rx2+2,
        f"Email: [{'ON' if em_on else 'OFF'}] ✉ ({'Running' if em_on else 'Disabled'})",
        cg(em_col | curses.A_BOLD))
    reg(em_toggle_row, rx2+2, rx2+45, "API_EM_TOGGLE")

    tbx = rx2 + 2
    w = draw_btn(win, tg_y+11, tbx, "📨 Send Test", "API_TG_TEST", color=CYAN); tbx += w+1
    w = draw_btn(win, tg_y+11, tbx, "✉ Email Test", "API_EM_TEST", color=CYAN)

    # ── Footer hint
    safe_addstr(win, max_y-2, 2,
        "[D] Demo  [R] Real  [1] One-way  [2] Hedge  [Enter] Confirm  B=Back  Tab/↑↓=API fields",
        cg(DIM))

    if api_editing:
        safe_addstr(win, max_y-1, 2, "Editing — Enter: done  |  Esc: cancel  |  Tab: next field", cg(YELLOW))

    
    from .base import draw_theme_bar
    draw_theme_bar(win, max_y, max_x)
    win.refresh()
