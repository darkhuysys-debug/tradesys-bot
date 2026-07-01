from .colors import cg
import curses
import os
from .base import draw_box, safe_addstr, draw_btn, reg, clear_clicks, cg, GREEN, RED, YELLOW, CYAN, WHITE, DIM
from .colors import init_colors
from updates.update import get_status, check_update_async, install_update_async, rollback_async, get_local_version

BOT_DIR = "/opt/tradesys_bot"


def _clamp_text(win, y, x, text, attr=0):
    try:
        max_y, max_x = win.getmaxyx()
        if y < 0 or y >= max_y or x < 0:
            return
        avail = max_x - x
        if avail <= 0:
            return
        if len(text) > avail:
            text = text[:avail]
        win.addstr(y, x, text, attr)
    except Exception:
        pass


_EXTS = {
    ".py": "PY", ".json": "JSON", ".sh": "SH", ".yml": "YAML", ".yaml": "YAML",
    ".txt": "TXT", ".md": "MD", ".html": "HTML", ".css": "CSS", ".js": "JS",
    ".deb": "DEB", ".tar.gz": "TAR", ".gz": "GZ", ".zip": "ZIP",
    ".cfg": "CFG", ".conf": "CONF", ".ini": "INI", ".env": "ENV",
    ".db": "DB", ".sql": "SQL", ".csv": "CSV", ".log": "LOG",
    ".desktop": "DESK", ".png": "IMG", ".jpg": "IMG", ".svg": "IMG",
}

_DESC = {
    "__init__.py": "Package init",
    "main.py": "Entrypoint & event loop",
    "config.py": "Config loader (strategy, API, risk)",
    "state.py": "Global bot state",
    "engine.py": "Trading engine chính",
    "executor.py": "Thực thi lệnh (buy/sell/cancel)",
    "bybit_api.py": "Kết nối API Bybit",
    "indicators.py": "Chỉ báo kỹ thuật (RSI/MACD/BB)",
    "signal_engine.py": "Sinh tín hiệu giao dịch",
    "risk_manager.py": "Quản lý rủi ro & position sizing",
    "multi_tf.py": "Phân tích đa khung thời gian",
    "regime.py": "Phát hiện chế độ thị trường",
    "trailing.py": "Trailing stop logic",
    "dashboard.py": "F1: Dashboard tổng quan",
    "running_screen.py": "F2: Lệnh đang chạy",
    "strategy_screen.py": "F3: Chiến lược",
    "logs_screen.py": "F4: Logs",
    "mode_screen.py": "F5: Mode/API",
    "symbols_screen.py": "F6: Quản lý symbols",
    "alerts_screen.py": "F7: Alert manager",
    "update_screen.py": "F8: Update Manager",
    "menu_screen.py": "Màn hình menu chính",
    "base.py": "Base UI helpers",
    "colors.py": "Theme & màu sắc",
    "update.py": "Logic update GitHub",
    "VERSION": "Phiên bản hiện tại",
    "uninstall.sh": "Gỡ cài đặt bot",
    "TradeSyS.desktop": "Desktop entry",
    "Uninstall_TradeSyS.desktop": "Desktop entry gỡ cài",
}

_HIDE = {"__pycache__", ".pyc", ".git", "backups", "updates", "tradesys-pkg"}

_NAME_W = 30
_TAG_W = 5
_SIZE_W = 9
_DESC_W = 22


def _scan_bot_files(path=None, rel=""):
    path = path or BOT_DIR
    rows = []
    try:
        with os.scandir(path) as it:
            for entry in sorted(it, key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.name in _HIDE or entry.name.startswith("."):
                    continue
                cur_rel = os.path.join(rel, entry.name) if rel else entry.name
                if entry.is_dir(follow_symlinks=False):
                    rows.append({
                        "name": entry.name,
                        "path": cur_rel,
                        "type": "dir",
                        "size": "—",
                        "ext": "DIR",
                        "desc": "",
                        "color": CYAN,
                    })
                    rows.extend(_scan_bot_files(entry.path, cur_rel))
                else:
                    _, ext = os.path.splitext(entry.name)
                    ext_key = ext.lower()
                    try:
                        size = entry.stat().st_size
                        if size >= 1024 * 1024:
                            size_str = f"{size / (1024 * 1024):.1f} MB"
                        elif size >= 1024:
                            size_str = f"{size / 1024:.1f} KB"
                        else:
                            size_str = f"{size} B"
                    except Exception:
                        size_str = "?"
                    tag = _EXTS.get(ext_key, ext_key.lstrip(".") if ext_key else "FILE")
                    if tag in ("PY", "SH", "DEB"):
                        color = GREEN
                    elif tag in ("JSON", "YAML", "CFG", "CONF", "INI", "ENV"):
                        color = YELLOW
                    elif tag in ("TXT", "MD", "LOG"):
                        color = WHITE
                    else:
                        color = DIM
                    rows.append({
                        "name": entry.name,
                        "path": cur_rel,
                        "type": "file",
                        "size": size_str,
                        "ext": tag,
                        "desc": _DESC.get(entry.name, ""),
                        "color": color,
                    })
    except PermissionError:
        pass
    return rows


def _get_bot_files():
    try:
        return _scan_bot_files()
    except Exception:
        return []


def _format_row(row, max_x):
    if row["type"] == "dir":
        prefix = "> "
        name = row["name"]
    else:
        prefix = "  "
        name = row["name"]
    desc = row.get("desc", "")
    name_w = _NAME_W
    tag_w = _TAG_W
    size_w = _SIZE_W
    desc_w = _DESC_W
    hdr = f"{'NAME':<{name_w}} {'TYPE':>{tag_w}} {'SIZE':>{size_w}} {'DESC':<{desc_w}}"
    total_table = name_w + tag_w + size_w + desc_w + 3
    avail_name = max_x - 2 - total_table - 2
    if avail_name < 10:
        avail_name = 10
    if len(name) > avail_name:
        name = name[:max(0, avail_name - 3)] + "..."
    if len(desc) > desc_w:
        desc = desc[:max(0, desc_w - 3)] + "..."
    left = f"{prefix}{name:<{name_w}}"
    tag = row["ext"].rjust(tag_w)
    size = row["size"].rjust(size_w)
    desc_padded = desc.ljust(desc_w) if desc else ""
    return left, tag, size, desc_padded


def draw_update_screen(win, state):
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()
    from .base import draw_header
    mode = state.get("f8_mode") if isinstance(state, dict) else getattr(state, "f8_mode", "update")
    title_map = {"update": "UPDATE", "files": "BOT FILES", "guide": "UPGRADE GUIDE"}
    title = title_map.get(mode, "UPDATE")
    draw_header(win, max_x, title, state)

    y0 = 3
    status = get_status()
    local_ver = get_local_version()
    remote_ver = status.get("remote_version") or "—"
    files = status.get("files", [])
    checking = status.get("checking", False)
    error = status.get("error")
    progress = status.get("progress", 0)
    log = status.get("log", [])
    available = status.get("available", False)
    done = status.get("done", False)

    if mode == "files":
        rows = getattr(state, "f8_file_rows", [])
        if not rows:
            rows = _get_bot_files()
            state.f8_file_rows = rows
            state.f8_file_scroll = 0
            state.f8_file_sel = 0
        draw_file_browser(win, state, max_y, max_x, y0)
    elif mode == "guide":
        draw_guide_screen(win, state)
    else:
        draw_update_manager(win, state, max_y, max_x, y0, local_ver, remote_ver, files, checking, error, progress, log, available, done, status.get("downloading", False))

    
    from .base import draw_theme_bar
    draw_theme_bar(win, max_y, max_x)
    win.refresh()



_F8_TABS = [
    ("Update Manager", "UPDATE_SWITCH_UPDATE"),
    ("File List", "UPDATE_FILELIST"),
    ("Upgrade Guide", "UPDATE_GUIDE"),
]

def _draw_f8_tabs(win, max_x, y0, state):
    tx = 2
    mode = getattr(state, "f8_mode", "update")
    for label, action in _F8_TABS:
        is_active = (action == "UPDATE_SWITCH_UPDATE" and mode == "update") or \
                    (action == "UPDATE_FILELIST" and mode == "files") or \
                    (action == "UPDATE_GUIDE" and mode == "guide")
        attr = (cg(CYAN) | curses.A_BOLD | curses.A_UNDERLINE) if is_active else cg(DIM)
        text = f" {label} "
        safe_addstr(win, y0, tx, text, attr)
        try:
            reg(y0, tx, tx + len(text) - 1, action)
        except Exception:
            pass
        tx += len(text) + 1

def draw_update_manager(win, state, max_y, max_x, y0, local_ver, remote_ver, files, checking, error, progress, log, available, done, downloading):
    safe_addstr(win, y0, 2, "UPDATE MANAGER", cg(GREEN) | curses.A_BOLD)
    title_len = 15
    safe_addstr(win, y0, 2 + title_len, "─" * min(max(1, max_x - 2 - title_len), 200), cg(GREEN))

    info_y = y0 + 1
    safe_addstr(win, info_y, 2, "Local: ", cg(WHITE))
    lv = local_ver.lstrip("v")
    rv = remote_ver.lstrip("v")
    dv = remote_ver if remote_ver == local_ver else rv
    safe_addstr(win, info_y, 8, lv, cg(CYAN) | curses.A_BOLD)
    rv_color = GREEN if (rv != lv) else DIM
    safe_addstr(win, info_y, 22, " Remote: ", cg(WHITE))
    safe_addstr(win, info_y, 30, rv, cg(rv_color))

    if available and rv > lv:
        safe_addstr(win, info_y, max_x - 16, "NEW!", cg(GREEN) | curses.A_BOLD)

    list_y = info_y + 2
    avail_h = max_y - list_y - 12
    list_h = max(6, avail_h) if avail_h > 6 else avail_h
    if list_h < 3:
        list_h = 3

    draw_box(win, list_y, 0, list_h, max_x, "PATCH FILES", GREEN)

    if checking:
        safe_addstr(win, list_y + 2, 2, "⟳  Checking for updates...", cg(YELLOW) | curses.A_BOLD)
        safe_addstr(win, list_y + 3, 2, "    Contacting GitHub API...", cg(DIM))
    elif error:
        safe_addstr(win, list_y + 2, 2, f"✗  {error}", cg(RED))
        if checking:
            safe_addstr(win, list_y + 3, 2, "    Retrying...", cg(DIM))
        else:
            safe_addstr(win, list_y + 3, 2, "    Press [Scan Update] to retry", cg(DIM))
    elif not files and not checking:
        safe_addstr(win, list_y + 2, 2, "No updates available.", cg(DIM))
        safe_addstr(win, list_y + 3, 2, "Press [Scan Update] to check", cg(DIM))
    else:
        safe_addstr(win, list_y + 1, 2, f"{len(files)} file(s) to update:", cg(WHITE))
        for i, finfo in enumerate(files[:list_h - 3]):
            if list_y + 2 + i >= list_y + list_h - 1:
                break
            path = finfo.get("path", "?")
            ftype = finfo.get("type", "stable")
            note = finfo.get("note", "")
            is_beta = ftype == "beta"
            icon = "🟡" if is_beta else "🟢"
            icon_color = YELLOW if is_beta else GREEN

            safe_addstr(win, list_y + 2 + i, 2, icon, icon_color | curses.A_BOLD)
            safe_addstr(win, list_y + 2 + i, 5, path[:max_x - 30], cg(WHITE))

            tag_x = max(8, max_x - 18)
            safe_addstr(win, list_y + 2 + i, tag_x, ftype.upper(), icon_color)
            if note:
                safe_addstr(win, list_y + 2 + i, tag_x + 10, f"· {note[:25]}", cg(DIM))
                safe_addstr(win, list_y + 2 + i, tag_x + 35, path[:max_x - tag_x - 38], cg(DIM))
            elif len(path) > max_x - 38:
                overflow = path[max_x - 38:]
                safe_addstr(win, list_y + 2 + i, max_x - len(overflow) - 18, overflow, cg(DIM))

    status_y = list_y + list_h + 1
    safe_addstr(win, status_y, 0, "─" * max(1, max_x), cg(GREEN))

    if progress > 0 and progress < 100 and downloading:
        bar_w = max_x - 28
        filled = int(bar_w * progress / 100)
        bar = f"Downloading [{'█' * filled}{'░' * (bar_w - filled)}] {progress}%"
        safe_addstr(win, status_y + 1, 2, bar, cg(YELLOW))
    elif done:
        safe_addstr(win, status_y + 1, 2, "✓  Update complete! Restarting bot...", cg(GREEN) | curses.A_BOLD)
    elif error and not checking:
        safe_addstr(win, status_y + 1, 2, f"✗  {error}", cg(RED))
    else:
        msg = f"Ready · {local_ver}"
        if checking:
            msg = f"Checking... (local {local_ver})"
        safe_addstr(win, status_y + 1, 2, msg, cg(GREEN))

    log_y = status_y + 3
    log_h = max(4, max_y - log_y - 2)
    if log_h >= 4 and max_y - log_y > 5:
        draw_box(win, log_y, 0, log_h, max_x, "LOG", DIM)
        recent = log[-log_h + 1:] if log else []
        for i, line in enumerate(recent):
            if i >= log_h - 1:
                break
            safe_addstr(win, log_y + 1 + i, 1, line[:max_x - 2], cg(DIM))

    btn_y = max_y - 3
    if done:
        safe_addstr(win, btn_y, 2, "Update complete! Restarting bot...", cg(GREEN) | curses.A_BOLD)
        bx = 2
        if bx + 8 < max_x:
            w = draw_btn(win, btn_y, bx, "Back", "BACK", color=RED)
    else:
        bx = 2
        if files and available and not checking and not done and not downloading:
            w = draw_btn(win, btn_y, bx, "Download & Install", "UPDATE_INSTALL", color=GREEN)
            bx += w + 2
        if bx + 18 < max_x:
            w = draw_btn(win, btn_y, bx, "Scan Update", "UPDATE_SCAN", color=CYAN)
            bx += w + 2
        if bx + 20 < max_x:
            w = draw_btn(win, btn_y, bx, "File List", "UPDATE_FILELIST", color=YELLOW)
            bx += w + 2
        if bx + 14 < max_x:
            w = draw_btn(win, btn_y, bx, "Guide", "UPDATE_GUIDE", color=CYAN)
            bx += w + 2
        if bx + 8 < max_x:
            w = draw_btn(win, btn_y, bx, "Back", "BACK", color=RED)


def draw_file_browser(win, state, max_y, max_x, y0):
    safe_addstr(win, y0, 2, "BOT FILE MANAGER", cg(CYAN) | curses.A_BOLD)
    title_len = 18
    safe_addstr(win, y0, 2 + title_len, "─" * max(1, max_x - 2 - title_len), cg(CYAN))

    path_y = y0 + 1
    safe_addstr(win, path_y, 2, f"Path: {BOT_DIR}", cg(DIM))

    file_rows = getattr(state, "f8_file_rows", [])
    scroll = getattr(state, "f8_file_scroll", 0)
    sel = getattr(state, "f8_file_sel", 0)

    list_y = path_y + 2
    avail_h = max_y - list_y - 6
    list_h = max(10, avail_h) if avail_h > 10 else avail_h
    if list_h < 6:
        list_h = 6

    name_x = 2
    tag_x = name_x + _NAME_W + 1
    size_x = tag_x + _TAG_W + 1
    desc_x = size_x + _SIZE_W + 1
    max_desc = max_x - desc_x - 2
    total_w = _NAME_W + _TAG_W + _SIZE_W + _DESC_W + 4
    max_desc = max(4, max_x - desc_x - 2)
    hdr_line = f"{'NAME':<{_NAME_W}} {'TYPE':>{_TAG_W}} {'SIZE':>{_SIZE_W}} {'DESC':<{_DESC_W}}"
    draw_box(win, list_y, 0, list_h, max_x, "BOT FILES", CYAN)

    if not file_rows:
        safe_addstr(win, list_y + 2, name_x, "No files found.", cg(DIM))
    else:
        hdr_display = hdr_line[:max(2, max_x - 4)] if len(hdr_line) > max_x - 4 else hdr_line
        safe_addstr(win, list_y, name_x, hdr_display, cg(CYAN) | curses.A_BOLD)
        max_visible = list_h - 2
        if sel < scroll:
            scroll = sel
        elif sel >= scroll + max_visible:
            scroll = sel - max_visible + 1
        scroll = max(0, min(scroll, max(0, len(file_rows) - max_visible)))
        state.f8_file_scroll = scroll

        for i in range(max_visible):
            idx = scroll + i
            if idx >= len(file_rows):
                break
            row = file_rows[idx]
            row_y = list_y + 1 + i
            is_sel = (idx == sel)
            left, tag, size, desc = _format_row(row, max_x)
            if is_sel:
                safe_addstr(win, row_y, 1, " " * (max_x - 2), cg(CYAN) | curses.A_BOLD)
                safe_addstr(win, row_y, name_x, left, cg(WHITE))
                safe_addstr(win, row_y, tag_x, tag, cg(WHITE))
                safe_addstr(win, row_y, size_x, size, cg(WHITE))
            else:
                safe_addstr(win, row_y, name_x, left, cg(row["color"]))
                safe_addstr(win, row_y, tag_x, tag, cg(DIM))
                safe_addstr(win, row_y, size_x, size, cg(DIM))
            if desc and max_desc > 2:
                d = desc
                if len(d) > _DESC_W:
                    d = d[:_DESC_W - 2] + ".."
                safe_addstr(win, row_y, desc_x, d.ljust(min(_DESC_W, max_desc)), cg(DIM if not is_sel else WHITE))

    info_y = list_y + list_h + 1
    total = len(file_rows)
    dirs = sum(1 for r in file_rows if r["type"] == "dir")
    py_files = sum(1 for r in file_rows if r.get("ext") == "PY")
    safe_addstr(win, info_y, 0, "─" * max(1, max_x), cg(CYAN))
    safe_addstr(win, info_y + 1, 2, f"Total: {total} items  |  Dirs: {dirs}  |  Python: {py_files}", cg(DIM))
    safe_addstr(win, info_y + 2, 2, "[↑↓] move  [R]refresh  [B]back", cg(DIM))

    btn_y = max_y - 3
    bx = 2
    if bx + 20 < max_x:
        w = draw_btn(win, btn_y, bx, "Download & Install", "UPDATE_INSTALL", color=GREEN)
        bx += w + 2
    if bx + 18 < max_x:
        w = draw_btn(win, btn_y, bx, "Scan Update", "UPDATE_SCAN", color=CYAN)
        bx += w + 2
    if bx + 20 < max_x:
        w = draw_btn(win, btn_y, bx, "File List", "UPDATE_FILELIST", color=YELLOW)
        bx += w + 2
    if bx + 8 < max_x:
        w = draw_btn(win, btn_y, bx, "Back", "BACK", color=RED)


_GUIDE_FILE_W = 16
_GUIDE_MODULE_W = 8
_GUIDE_TAB_W = 6
_GUIDE_DESC_W = 22
_GUIDE_WHEN_W = 24


def _trunc(text, width):
    if len(text) > width:
        return text[:max(0, width - 2)] + ".."
    return text


_GUIDE_ROWS = [
    {"file": "engine.py", "module": "bot", "tab": "CORE", "desc": "Trading engine chính", "when": "Đổi logic chạy bot / strategy flow"},
    {"file": "executor.py", "module": "bot", "tab": "CORE", "desc": "Thực thi lệnh (buy/sell/cancel)", "when": "Thay đổi cách đặt lệnh / order type"},
    {"file": "bybit_api.py", "module": "bot", "tab": "CORE", "desc": "Kết nối API Bybit", "when": "Đổi endpoint, auth, websocket"},
    {"file": "indicators.py", "module": "bot", "tab": "CORE", "desc": "Chỉ báo kỹ thuật (RSI/MACD/BB)", "when": "Thay đổi chiến lược kỹ thuật"},
    {"file": "signal_engine.py", "module": "bot", "tab": "CORE", "desc": "Sinh tín hiệu giao dịch", "when": "Tinh chỉnh logic BUY/SELL/WAIT"},
    {"file": "risk_manager.py", "module": "bot", "tab": "CORE", "desc": "Quản lý rủi ro & position sizing", "when": "Đổi TP/SL / khẩu vị rủi ro"},
    {"file": "multi_tf.py", "module": "bot", "tab": "CORE", "desc": "Phân tích đa khung thời gian", "when": "Đa khung TG, confirm tín hiệu"},
    {"file": "regime.py", "module": "bot", "tab": "CORE", "desc": "Phát hiện chế độ thị trường", "when": "Bot tự động điều chỉnh theo thị trường"},
    {"file": "trailing.py", "module": "bot", "tab": "CORE", "desc": "Trailing stop logic", "when": "Tinh chỉnh trailing stop"},
    {"file": "config.py", "module": "core", "tab": "CORE", "desc": "Config loader", "when": "Thay đổi cấu hình mặc định"},
    {"file": "state.py", "module": "core", "tab": "CORE", "desc": "Global bot state", "when": "Thêm trạng thái mới"},
    {"file": "main.py", "module": "core", "tab": "CORE", "desc": "Entrypoint & event loop", "when": "Thay đổi flow chính, key handling"},
    {"file": "dashboard.py", "module": "ui", "tab": "F1", "desc": "Dashboard tổng quan", "when": "Sửa giao diện F1, thêm panel"},
    {"file": "running_screen.py", "module": "ui", "tab": "F2", "desc": "Lệnh đang chạy", "when": "Sửa hiển thị positions/trades"},
    {"file": "strategy_screen.py", "module": "ui", "tab": "F3", "desc": "Chiến lược", "when": "Sửa input strategy params"},
    {"file": "logs_screen.py", "module": "ui", "tab": "F4", "desc": "Logs", "when": "Sửa hiển thị log"},
    {"file": "mode_screen.py", "module": "ui", "tab": "F5", "desc": "Mode/API", "when": "Sửa màn hình đổi mode"},
    {"file": "symbols_screen.py", "module": "ui", "tab": "F6", "desc": "Quản lý symbols", "when": "Sửa danh sách theo dõi"},
    {"file": "alerts_screen.py", "module": "ui", "tab": "F7", "desc": "Alert manager", "when": "Sửa Telegram/Email alerts"},
    {"file": "update_screen.py", "module": "ui", "tab": "F8", "desc": "Update Manager", "when": "Sửa giao diện update"},
    {"file": "menu_screen.py", "module": "ui", "tab": "MENU", "desc": "Màn hình menu chính", "when": "Sửa menu, thêm item mới"},
    {"file": "base.py", "module": "ui", "tab": "SHARED", "desc": "Base UI helpers", "when": "Sửa vẽ box, màu, click"},
    {"file": "colors.py", "module": "ui", "tab": "SHARED", "desc": "Theme & màu sắc", "when": "Đổi theme màu"},
    {"file": "update.py", "module": "updates", "tab": "F8", "desc": "Logic update GitHub", "when": "Sửa cách download/install update"},
    {"file": "VERSION", "module": "core", "tab": "CORE", "desc": "Phiên bản hiện tại", "when": "Tăng version khi release"},
]


def draw_guide_screen(win, state):
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()
    from .base import draw_header
    draw_header(win, max_x, state.f8_mode or "guide", state)

    y0 = 3
    safe_addstr(win, y0, 2, "UPGRADE & MODIFICATION GUIDE", cg(CYAN) | curses.A_BOLD)
    title_len = 30
    safe_addstr(win, y0, 2 + title_len, "─" * max(1, max_x - 2 - title_len), cg(CYAN))

    path_y = y0 + 1
    safe_addstr(win, path_y, 2, "Huong dan sua tung phan cua bot", cg(DIM))

    scroll = getattr(state, "f8_guide_scroll", 0)
    sel = getattr(state, "f8_guide_sel", 0)

    list_y = path_y + 2
    avail_h = max_y - list_y - 8
    list_h = max(10, avail_h) if avail_h > 10 else avail_h
    if list_h < 6:
        list_h = 6

    name_x = 2
    mod_x = name_x + _GUIDE_FILE_W + 1
    tab_x = mod_x + _GUIDE_MODULE_W + 1
    desc_x = tab_x + _GUIDE_TAB_W + 1
    when_x = desc_x + _GUIDE_DESC_W + 1
    max_when = max_x - when_x - 2

    draw_box(win, list_y, 0, list_h, max_x, "UPGRADE & MODIFICATION GUIDE", CYAN)
    safe_addstr(win, list_y, name_x, f"{'FILE':<{_GUIDE_FILE_W}}{'MODULE':>{_GUIDE_MODULE_W}} {'TAB':>{_GUIDE_TAB_W}} {'MUC DICH':<{_GUIDE_DESC_W}} {'KHI NAO SUA':<{_GUIDE_WHEN_W}}"[:max_x-4], cg(CYAN) | curses.A_BOLD)

    rows = _GUIDE_ROWS
    max_visible = list_h - 2
    if sel < scroll:
        scroll = sel
    elif sel >= scroll + max_visible:
        scroll = sel - max_visible + 1
    scroll = max(0, min(scroll, max(0, len(rows) - max_visible)))
    state.f8_guide_scroll = scroll
    state.f8_guide_sel = sel

    for i in range(max_visible):
        idx = scroll + i
        if idx >= len(rows):
            break
        row = rows[idx]
        row_y = list_y + 1 + i
        is_sel = (idx == sel)

        f = _trunc(row["file"], _GUIDE_FILE_W)
        m = _trunc(row["module"], _GUIDE_MODULE_W)
        t = _trunc(row["tab"], _GUIDE_TAB_W)
        d = _trunc(row["desc"], _GUIDE_DESC_W)
        w = _trunc(row["when"], _GUIDE_WHEN_W)

        if is_sel:
            safe_addstr(win, row_y, 1, " " * (max_x - 2), cg(CYAN) | curses.A_BOLD)
            safe_addstr(win, row_y, name_x, f.ljust(_GUIDE_FILE_W), cg(WHITE))
            safe_addstr(win, row_y, mod_x, m.rjust(_GUIDE_MODULE_W), cg(WHITE))
            safe_addstr(win, row_y, tab_x, t.rjust(_GUIDE_TAB_W), cg(WHITE))
            safe_addstr(win, row_y, desc_x, d.ljust(_GUIDE_DESC_W), cg(WHITE))
            if max_when > 2:
                safe_addstr(win, row_y, when_x, w[:max_when].ljust(max_when), cg(WHITE))
        else:
            safe_addstr(win, row_y, name_x, f.ljust(_GUIDE_FILE_W), cg(WHITE))
            safe_addstr(win, row_y, mod_x, m.rjust(_GUIDE_MODULE_W), cg(DIM))
            safe_addstr(win, row_y, tab_x, t.rjust(_GUIDE_TAB_W), cg(YELLOW))
            safe_addstr(win, row_y, desc_x, d.ljust(_GUIDE_DESC_W), cg(GREEN))
            if max_when > 2:
                safe_addstr(win, row_y, when_x, w[:max_when].ljust(max_when), cg(DIM))

        if is_sel:
            try:
                reg(row_y, name_x, _GUIDE_FILE_W, f"GUIDE_ROW_{idx}")
                reg(row_y, mod_x, _GUIDE_MODULE_W, f"GUIDE_ROW_{idx}")
                reg(row_y, tab_x, _GUIDE_TAB_W, f"GUIDE_ROW_{idx}")
                reg(row_y, desc_x, _GUIDE_DESC_W, f"GUIDE_ROW_{idx}")
                if max_when > 2:
                    reg(row_y, when_x, max_when, f"GUIDE_ROW_{idx}")
            except Exception:
                pass

    info_y = list_y + list_h + 1
    safe_addstr(win, info_y, 0, "─" * max(1, max_x), cg(CYAN))
    safe_addstr(win, info_y + 1, 2, f"Total: {len(rows)} files documented", cg(DIM))
    safe_addstr(win, info_y + 1, max(2, max_x - 16), "[↑↓] move  [B]back", cg(DIM))

    btn_y = max_y - 5
    bx = 2
    if bx + 20 < max_x:
        w = draw_btn(win, btn_y, bx, "Update Manager", "UPDATE_SWITCH_UPDATE", color=GREEN)
        bx += w + 2
    if bx + 14 < max_x:
        w = draw_btn(win, btn_y, bx, "File List", "UPDATE_FILELIST", color=YELLOW)
        bx += w + 2
    if bx + 10 < max_x:
        w = draw_btn(win, btn_y, bx, "Guide", "UPDATE_SWITCH_GUIDE", color=CYAN)
        bx += w + 2
    if bx + 8 < max_x:
        w = draw_btn(win, btn_y, bx, "Back", "BACK", color=RED)
