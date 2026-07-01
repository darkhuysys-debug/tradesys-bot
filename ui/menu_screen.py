import curses
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from state import state
from .base import safe_addstr, draw_btn, reg, clear_clicks, get_version
from .colors import cg, GREEN, WHITE, CYAN, YELLOW, RED, DIM

LOGO = [
    " ████████╗ ██████╗  █████╗ ██████╗ ███████╗",
    " ╚══██╔══╝ ██╔══██╗██╔══██╗██╔══██╗██╔════╝",
    "    ██║    ██████╔╝███████║██║  ██║█████╗  ",
    "    ██║    ██╔══██╗██╔══██║██║  ██║██╔══╝  ",
    "    ██║    ██║  ██║██║  ██║██████╔╝███████╗",
    "    ╚═╝    ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝",
    "",
    " «  ██╗  ██╗██╗   ██╗██╗   ██╗  »",
    " «  ██║  ██║██║   ██║╚██╗ ██╔╝  »",
    " «  ███████║██║   ██║ ╚████╔╝   »",
    " «  ██╔══██║██║   ██║  ╚██╔╝    »",
    " «  ██║  ██║╚██████╔╝   ██║     »",
    " «  ╚═╝  ╚═╝ ╚═════╝    ╚═╝     »",
]

# (label, action, description)
MENU_ITEMS = [
    ("▶  Dashboard",       "DASHBOARD",    "F1  Overview + Quick Actions"),
    ("▶  Bot Control",     "RUNNING",      "F2  Xem lệnh đang chạy"),
    ("▶  Strategy Config", "STRATEGY",     "F3  Indicators / Risk / Params"),
    ("▶  Mode & API",      "MODE_SELECT",  "F5  Demo/Real · Position Mode"),
    ("▶  Symbols",         "SYMBOLS",      "F6  Quản lý watchlist"),
    ("▶  Logs",            "LOGS",         "F4  Bot logs"),
    ("★  Alert Manager",   "ALERTS",       "F7  Thông báo realtime"),
    ("",                   "",             ""),
    ("✖  Thoát",      "EXIT",         "Thoát chương trình"),
]

# Rows where each active menu item is drawn (populated in draw_menu)
_item_rows = []
# Tracks the last-drawn selection so we can leave a fading "trail" behind
# as the cursor moves between rows — purely cosmetic, makes ↑↓ feel like
# it glides rather than jumps.
_prev_sel = 0

def get_hover_sel(mouse_y):
    """Return menu_sel index for a given mouse row, or -1 if not on any item."""
    for idx, row in enumerate(_item_rows):
        if mouse_y == row:
            return idx
    return -1

def draw_menu(win, menu_sel=0, hover_sel=-1):
    global _item_rows, _prev_sel
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()

    try:
        win.attron(cg(GREEN))
        win.border()
        win.attroff(cg(GREEN))
    except curses.error:
        pass

    # Back button — top-left
    back_label = " ◀ Back "
    safe_addstr(win, 0, 2, back_label, cg(CYAN) | curses.A_BOLD)
    reg(0, 2, 2 + len(back_label) - 1, "BACK")

    ver_label = f" Trade SyS {get_version()} "
    safe_addstr(win, 0, 2 + len(back_label) + 1, ver_label, cg(GREEN) | curses.A_BOLD)

    mode_tag = state.mode.upper() if state.mode else "DEMO"
    pos_mode = getattr(state, 'position_mode', 'one-way')
    pos_tag  = "1W" if pos_mode == "one-way" else "HEDGE"
    api_ok   = bool(state.bybit_api_key)
    bot_tag  = "● RUNNING" if state.running else "○ STOPPED"
    bot_col  = GREEN if state.running else RED

    logo_y = max(2, (max_y - len(LOGO) - 12) // 2)
    for i, line in enumerate(LOGO):
        x = max(1, (max_x - len(line)) // 2)
        safe_addstr(win, logo_y + i, x, line, cg(GREEN) | curses.A_BOLD)

    tag = "HUY  ·  ONE-CLICK BYBIT FUTURES BOT  ·  v1.1.25"
    ty  = logo_y + len(LOGO) + 1
    safe_addstr(win, ty, (max_x - len(tag)) // 2, tag, cg(GREEN))

    sb_y    = ty + 1
    mode_col = GREEN if mode_tag == "DEMO" else CYAN
    key_str  = (state.bybit_api_key[:6] + "...") if api_ok else "None"
    key_col  = GREEN if api_ok else YELLOW

    sx = (max_x - 60) // 2
    safe_addstr(win, sb_y, sx, " Mode: ", cg(WHITE))
    safe_addstr(win, sb_y, sx + 7, mode_tag, cg(mode_col) | curses.A_BOLD)
    safe_addstr(win, sb_y, sx + 7 + len(mode_tag), f"  |  Pos: {pos_tag}  |  API: ", cg(WHITE))
    kx = sx + 7 + len(mode_tag) + 20
    safe_addstr(win, sb_y, kx, key_str, cg(key_col))
    safe_addstr(win, sb_y, kx + len(key_str), "  |  Bot: ", cg(WHITE))
    safe_addstr(win, sb_y, kx + len(key_str) + 10, bot_tag, cg(bot_col) | curses.A_BOLD)

    menu_y = sb_y + 2
    title  = "──── MAIN MENU ────"
    safe_addstr(win, menu_y, (max_x - len(title)) // 2, title, cg(GREEN) | curses.A_BOLD)

    item_w = 28
    desc_w = 26
    item_x = (max_x - item_w - desc_w - 2) // 2

    _item_rows = []
    row     = menu_y + 1
    sel_idx = 0
    for label, action, desc in MENU_ITEMS:
        if not label:
            row += 1
            continue

        _item_rows.append(row)

        is_sel   = (sel_idx == menu_sel)
        is_trail = (sel_idx == _prev_sel and not is_sel and _prev_sel != menu_sel)
        hl       = curses.A_REVERSE if is_sel else 0
        # Exit stays RED, everything else GREEN
        color   = RED if action == "EXIT" else GREEN

        if is_trail:
            # Faded afterimage of where the cursor just was — dim, no reverse.
            row_attr  = cg(DIM)
            desc_attr = cg(DIM)
        else:
            row_attr  = cg(color) | hl | (curses.A_BOLD if is_sel else 0)
            desc_attr = cg(GREEN) | hl

        safe_addstr(win, row, item_x, f"{label:<{item_w}}", row_attr)
        if desc:
            safe_addstr(win, row, item_x + item_w + 1,
                        f"{desc:<{desc_w}}", desc_attr)
        if action:
            reg(row, item_x, item_x + item_w + desc_w, action)

        row     += 1
        sel_idx += 1

    _prev_sel = menu_sel

    footer = f"Trade SyS {get_version()}  ·  Click để chọn  ·  [↑↓] di chuyển  [Q] đóng"
    safe_addstr(win, max_y - 2, (max_x - len(footer)) // 2, footer, cg(GREEN))

    
    from .base import draw_theme_bar
    draw_theme_bar(win, max_y, max_x)
    win.refresh()
