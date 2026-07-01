import curses
import time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from state import state
from .base import safe_addstr, draw_btn, reg, clear_clicks, get_version, draw_header
from .colors import cg, GREEN, WHITE, YELLOW, RED, CYAN, DIM

LOG_FILTERS = ["ALL", "INFO", "WARN", "ERR", "OK"]

def _log_level(line):
    if "[ERROR]" in line or "[ERR]" in line:
        return "ERR"
    if "[WARN]" in line:
        return "WARN"
    if "[OK]" in line:
        return "OK"
    if "[INFO]" in line:
        return "INFO"
    return "INFO"

def draw_logs(win, state, scroll=0, log_filter="ALL"):
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()
    draw_header(win, max_x, "LOGS", state)

    # Filter bar
    fx = 2
    safe_addstr(win, 3, fx, "BOT LOGS  Filter:", cg(WHITE))
    fx += 8
    for f in LOG_FILTERS:
        is_sel = (log_filter == f)
        attr = (cg(GREEN) | curses.A_BOLD | curses.A_REVERSE) if is_sel else cg(DIM)
        lbl = f" {f} "
        safe_addstr(win, 3, fx, lbl, attr)
        reg(3, fx, fx + len(lbl) - 1, f"LOG_FILTER_{f}")
        fx += len(lbl) + 1
    clr_lbl = " ✖ Clear "
    safe_addstr(win, 3, max_x - len(clr_lbl) - 2, clr_lbl, cg(RED))
    reg(3, max_x - len(clr_lbl) - 2, max_x - 3, "LOG_CLEAR")

    log_top = 5
    log_bottom = max_y - 4
    visible = log_bottom - log_top
    logs = state.logs
    total = len(logs)
    if log_filter != "ALL":
        filtered = [l for l in logs if _log_level(l) == log_filter]
    else:
        filtered = logs
    shown = filtered[max(0, len(filtered) - visible - scroll):max(0, len(filtered) - scroll)]

    for i, line in enumerate(shown):
        y = log_top + i
        if y >= log_bottom:
            break
        col = (RED    if "[ERROR]" in line or "[ERR]" in line else
               YELLOW if "[WARN]"  in line else
               GREEN  if "[OK]"    in line else
               CYAN)
        # Parse: "[HH:MM:SS] [LEVEL] message"
        import re as _re
        m = _re.match(r"^\[?(\d{2}:\d{2}:\d{2})\]?\s*\[?([A-Z]+)\]?\s*(.*)", line)
        if m:
            ts, lvl, msg = m.group(1), m.group(2), m.group(3)
            safe_addstr(win, y, 1,  ts,              cg(DIM))
            safe_addstr(win, y, 11, f"{lvl:<6}",     cg(col) | curses.A_BOLD)
            safe_addstr(win, y, 18, msg[:max_x-20],  cg(WHITE))
        else:
            safe_addstr(win, y, 1, line[:max_x-2], cg(col))

    auto = "ON" if scroll == 0 else f"OFF (offset={scroll})"
    safe_addstr(win, max_y-4, 2, f"Total: {total}  |  Showing: {len(shown)} of {len(filtered)}  |  Auto-scroll: {auto}", cg(GREEN))

    try:
        win.attron(cg(GREEN))
        win.addstr(max_y-3, 0, "─" * max_x)
        win.attroff(cg(GREEN))
    except curses.error:
        pass

    bx = 2
    w = draw_btn(win, max_y-2, bx, "▲ Up", "LOG_UP"); bx += w+1
    w = draw_btn(win, max_y-2, bx, "▼ Down", "LOG_DOWN"); bx += w+1
    w = draw_btn(win, max_y-2, bx, "⏬ Bottom", "LOG_BOTTOM"); bx += w+1
    draw_btn(win, max_y-2, bx, "☰ Menu", "MENU", color=RED)

    hint = "↑↓ scroll  |  B=Back  Q=Menu  |  Filter click to filter"
    safe_addstr(win, max_y-2, max_x - len(hint) - 2, hint, cg(DIM))
    
    from .base import draw_theme_bar
    draw_theme_bar(win, max_y, max_x)
    win.refresh()
