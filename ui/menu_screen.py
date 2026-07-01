import curses
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from state import state
from .base import safe_addstr, draw_btn, reg, clear_clicks, get_version
from .colors import cg, GREEN, WHITE, CYAN, YELLOW, RED, DIM

LOGO = [
    "   ████████╗ ██████╗  █████╗ ██████╗ ███████╗",
    "   ╚══██╔══╝ ██╔══██╗██╔══██╗██╔══██╗██╔════╝",
    "      ██║    ██████╔╝███████║██║  ██║█████╗  ",
    "      ██║    ██╔══██╗██╔══██║██║  ██║██╔══╝  ",
    "      ██║    ██║  ██║██║  ██║██████╔╝███████╗",
    "      ╚═╝    ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝",
    "",
    "    «  ██╗  ██╗██╗   ██╗██╗   ██╗  »",
    "    «  ██║  ██║██║   ██║╚██╗ ██╔╝  »",
    "    «  ███████║██║   ██║ ╚████╔╝   »",
    "    «  ██╔══██║██║   ██║  ╚██╔╝    »",
    "    «  ██║  ██║╚██████╔╝   ██║     »",
    "    «  ╚═╝  ╚═╝ ╚═════╝    ╚═╝     »",
]

MENU_ITEMS = [
    ("BOOT SYSTEM", "DASHBOARD", ""),
]

def get_hover_sel(mouse_y):
    return -1

def draw_menu(win, menu_sel=0, hover_sel=-1):
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()

    try:
        win.attron(cg(GREEN))
        win.border()
        win.attroff(cg(GREEN))
    except curses.error:
        pass

    ver = get_version()
    mode_tag = state.mode.upper() if state.mode else "DEMO"
    pos_tag  = "1W" if getattr(state, 'position_mode', 'one-way') == "one-way" else "HDG"
    api_ok   = bool(state.bybit_api_key)
    key_str  = (state.bybit_api_key[:6] + "..") if api_ok else "N/A"
    bot_tag  = "RUN" if state.running else "STOP"
    bot_col  = GREEN if state.running else RED

    logo_y = max(2, (max_y - len(LOGO) - 6) // 2)
    for i, line in enumerate(LOGO):
        x = max(1, (max_x - len(line)) // 2)
        safe_addstr(win, logo_y + i, x, line, cg(GREEN) | curses.A_BOLD)

    ty = logo_y + len(LOGO) + 1
    tag = f"HUY \u00b7 {ver}"
    safe_addstr(win, ty, (max_x - len(tag)) // 2, tag, cg(GREEN) | curses.A_BOLD)

    sb_y = ty + 1
    mode_col = GREEN if mode_tag == "DEMO" else CYAN
    parts = [
        (f"Mode: {mode_tag}", cg(mode_col) | curses.A_BOLD),
        (f"Pos: {pos_tag}", cg(WHITE)),
        (f"API: {key_str}", cg(GREEN if api_ok else YELLOW)),
        (f"Bot: {bot_tag}", cg(bot_col) | curses.A_BOLD),
    ]
    full = "  ".join(p[0] for p in parts)
    x = (max_x - len(full)) // 2
    for text, color in parts:
        safe_addstr(win, sb_y, x, text, color)
        x += len(text) + 2

    btn_y = sb_y + 2
    if btn_y < max_y - 4:
        w = draw_btn(win, btn_y, (max_x - 18) // 2, "BOOT SYSTEM", "DASHBOARD", color=GREEN, highlight=True)

    footer = f"Click BOOT SYSTEM  |  {ver}  |  [Q] exit"
    safe_addstr(win, max_y - 2, (max_x - len(footer)) // 2, footer, cg(DIM))

    from .base import draw_theme_bar
    draw_theme_bar(win, max_y, max_x)
    win.refresh()
