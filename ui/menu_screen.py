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
    "    «  ███████╗██╗   ██╗███████╗  »",
    "    «  ██╔════╝╚██╗ ██╔╝██╔════╝  »",
    "    «  ███████╗ ╚████╔╝ ███████╗  »",
    "    «  ╚════██║  ╚██╔╝  ╚════██║  »",
    "    «  ███████║   ██║   ███████║  »",
    "    «  ╚══════╝   ╚═╝   ╚══════╝  »",
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
    tag = f"Trade SyS \u00b7 {ver}"
    safe_addstr(win, ty, (max_x - len(tag)) // 2, tag, cg(GREEN) | curses.A_BOLD)

    sb_y = ty + 2
    box_w = min(max_x - 4, 60)
    bx = (max_x - box_w) // 2
    for bx_off in range(box_w):
        safe_addstr(win, sb_y, bx + bx_off, "─", cg(GREEN))
    safe_addstr(win, sb_y, bx, "┌", cg(GREEN))
    safe_addstr(win, sb_y, bx + box_w - 1, "┐", cg(GREEN))

    content = [
        (f"Mode: {mode_tag}", cg(GREEN if mode_tag == "DEMO" else CYAN) | curses.A_BOLD),
        (f"Pos: {pos_tag}", cg(WHITE)),
        (f"API: {key_str}", cg(GREEN if api_ok else YELLOW)),
        (f"Bot: {bot_tag}", cg(bot_col) | curses.A_BOLD),
    ]
    gap = (box_w - 2 - sum(len(c[0]) for c in content)) // max(len(content) - 1, 1)
    cx = bx + 1
    for text, color in content:
        safe_addstr(win, sb_y, cx, text, color)
        cx += len(text) + gap

    sb_y2 = sb_y + 1
    for bx_off in range(box_w):
        safe_addstr(win, sb_y2, bx + bx_off, "─", cg(GREEN))
    safe_addstr(win, sb_y2, bx, "└", cg(GREEN))
    safe_addstr(win, sb_y2, bx + box_w - 1, "┘", cg(GREEN))

    btn_y = sb_y2 + 2
    if btn_y < max_y - 4:
        w = draw_btn(win, btn_y, (max_x - 18) // 2, "BOOT SYSTEM", "DASHBOARD", color=GREEN, highlight=True)

    footer = f"Click BOOT SYSTEM  |  {ver}  |  [Q] exit"
    safe_addstr(win, max_y - 2, (max_x - len(footer)) // 2, footer, cg(DIM))

    from .base import draw_theme_bar
    draw_theme_bar(win, max_y, max_x)
    win.refresh()
