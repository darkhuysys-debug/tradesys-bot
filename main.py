#!/usr/bin/env python3
import curses
import sys
import os
import time
import threading
import smtplib
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from state import state
from config import load_config, save_config, apply_config_to_state, CONFIG_DIR
from bot.engine import start_bot, stop_bot
from ui.colors import init_colors, set_theme
from ui.base import get_action_at, flash_region, get_region_for_action
from ui.menu_screen import draw_menu, get_hover_sel
from ui.dashboard import draw_dashboard
from ui.logs_screen import draw_logs
from ui.strategy_screen import draw_strategy, FIELDS
from ui.running_screen import draw_running
from ui.mode_screen import draw_mode_select, draw_api_input, draw_mode_api_combined, APIFIELDS, _ensure_api_state
from ui.symbols_screen import draw_symbols, start_watchlist_fetcher, stop_watchlist_fetcher
from ui.alerts_screen import draw_alerts, push_alert, _ensure_alerts
from ui.update_screen import draw_update_screen, _GUIDE_ROWS

SCREEN_MENU        = "menu"
SCREEN_DASHBOARD   = "dashboard"
SCREEN_LOGS        = "logs"
SCREEN_STRATEGY    = "strategy"
SCREEN_RUNNING     = "running"
SCREEN_MODE_SELECT = "mode_select"
SCREEN_API_INPUT   = "api_input"
SCREEN_SYMBOLS     = "symbols"
SCREEN_ALERTS      = "alerts"
SCREEN_UPDATE      = "update"

def load_accounts(cfg):
    state.accounts = []
    key = state.bybit_api_key
    if key:
        masked = key[:4] + "***" + key[-4:] if len(key) > 8 else key
        state.accounts.append({
            "exchange":  "Bybit",
            "api_key":   masked,
            "balance":   state.equity,
            "connected": state.bybit_connected or state.mode == "demo",
        })

def _do_email_test(state, result_holder):
    try:
        import urllib.request, json
        api_key = getattr(state, 'sendgrid_api_key', '')
        to_addr = getattr(state, 'email_from', '')
        if not api_key or not to_addr:
            raise ValueError('Missing SendGrid API key or From email')
        payload = json.dumps({
            "personalizations": [{"to": [{"email": to_addr}]}],
            "from": {"email": to_addr},
            "subject": "Trade SyS Email Test",
            "content": [{"type": "text/plain", "value": "Trade Sys email notification - connection OK"}]
        }).encode()
        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
        result_holder["done"] = True
        result_holder["ok"]   = status in (200, 202)
        result_holder["msg"]  = f"SendGrid OK · status {status} · sent to {to_addr}"
    except Exception as e:
        result_holder["done"] = True
        result_holder["ok"]   = False
        result_holder["msg"]  = str(e)

def _do_api_test(api_key, api_secret, result_holder, demo=True):
    try:
        from bot.bybit_api import test_connection
        ok, msg = test_connection(api_key, api_secret, demo=demo)
        result_holder["done"] = True
        result_holder["ok"]   = ok
        result_holder["msg"]  = msg
    except Exception as e:
        result_holder["done"] = True
        result_holder["ok"]   = False
        result_holder["msg"]  = str(e)

def main(stdscr):
    curses.curs_set(0)
    curses.noecho()
    stdscr.nodelay(True)
    stdscr.timeout(100)          # shorter timeout → snappier hover response
    init_colors()
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)

    cfg = load_config()
    apply_config_to_state(cfg, state)
    load_accounts(cfg)
    # Start price fetcher if already connected from saved config
    if state.bybit_connected or state.mode == "demo":
        from ui.symbols_screen import _ensure_state as _sym_ensure, start_watchlist_fetcher as _swf
        _sym_ensure(state)
        _swf(state)

    screen         = SCREEN_MENU
    screen_history = []

    log_scroll    = 0
    strat_sel     = 0
    menu_sel      = 0
    menu_hover    = -1           # which menu row mouse is hovering over
    strat_editing = False
    strat_buf     = ""

    mode_tmp     = state.mode
    pos_mode_tmp = getattr(state, 'position_mode', 'one-way')

    api_sel       = 0
    api_editing   = False
    api_buf       = ""
    api_status    = ""
    api_status_ok = True
    api_testing   = False
    email_testing = False
    email_status  = ""
    email_status_ok = False
    email_test_res = {}
    api_test_res  = {}

    sym_sel       = 0
    sym_add_mode  = False
    sym_buf       = ""

    def go_to(new_screen):
        nonlocal screen
        screen_history.append(screen)
        screen = new_screen

    def go_back():
        nonlocal screen
        if screen_history:
            screen = screen_history.pop()

    while True:
        if (state.pending_confirm_action and
                time.time() >= state.pending_confirm_until):
            state.pending_confirm_action = None
            state.pending_confirm_until  = 0.0

        if api_testing and api_test_res.get("done"):
            api_testing          = False
            api_status_ok        = api_test_res["ok"]
            api_status           = api_test_res["msg"]
            state.bybit_connected = api_test_res["ok"]
            load_accounts(cfg)
            if state.bybit_connected:
                from ui.symbols_screen import _ensure_state as _sym_ensure
                _sym_ensure(state)
                start_watchlist_fetcher(state)
            api_test_res = {}

        if email_testing and email_test_res.get("done"):
            email_testing    = False
            email_status_ok  = email_test_res["ok"]
            email_status     = email_test_res["msg"]
            push_alert(state, "OK" if email_status_ok else "ERR",
                       f"Email: {email_status}")
            email_test_res = {}

        try:
            if screen == SCREEN_MENU:
                draw_menu(stdscr, menu_sel, menu_hover)
            elif screen == SCREEN_DASHBOARD:
                draw_dashboard(stdscr, state)
            elif screen == SCREEN_LOGS:
                draw_logs(stdscr, state, log_scroll)
            elif screen == SCREEN_STRATEGY:
                draw_strategy(stdscr, state, strat_sel, strat_editing, strat_buf)
            elif screen == SCREEN_RUNNING:
                draw_running(stdscr, state)
            elif screen in (SCREEN_MODE_SELECT, SCREEN_API_INPUT):
                draw_mode_api_combined(stdscr, mode_tmp, pos_mode_tmp,
                                       api_sel, api_editing, api_buf,
                                       api_status, api_status_ok, api_testing,
                                       email_status, email_status_ok, email_testing)
            elif screen == SCREEN_SYMBOLS:
                draw_symbols(stdscr, state)
            elif screen == SCREEN_ALERTS:
                draw_alerts(stdscr, state)
            elif screen == SCREEN_UPDATE:
                draw_update_screen(stdscr, state)
        except curses.error:
            pass

        try:
            key = stdscr.getch()
        except curses.error:
            key = -1

        if key == -1:
            continue

        action = None

        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()

                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_RELEASED):
                    action = get_action_at(my, mx)
                    # Clicking on a menu item also moves keyboard cursor there
                    if screen == SCREEN_MENU and action:
                        from ui.menu_screen import MENU_ITEMS
                        active_items = [item for item in MENU_ITEMS if item[1]]
                        for i, item in enumerate(active_items):
                            if item[1] == action:
                                menu_sel = i
                                break
            except curses.error:
                pass

        elif key == curses.KEY_F8 and not strat_editing and not api_editing:
            state.f8_mode = "update"
            go_to(SCREEN_UPDATE)
        elif key == curses.KEY_F9 and not strat_editing and not api_editing:
            state.f8_mode = "guide"
            state.f8_guide_scroll = 0
            go_to(SCREEN_UPDATE)
        elif key == curses.KEY_F10 and not strat_editing and not api_editing:
            state.f8_mode = "files"
            state.f8_file_rows = []
            go_to(SCREEN_UPDATE)
        elif screen == SCREEN_STRATEGY and strat_editing:
            if   key == 27:
                strat_editing = False; strat_buf = ""
            elif key in (curses.KEY_ENTER, 10, 13):
                fkey, _, ftype = FIELDS[strat_sel]
                try: setattr(state, fkey, ftype(strat_buf))
                except ValueError: pass
                strat_editing = False; strat_buf = ""
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                strat_buf = strat_buf[:-1]
            elif 32 <= key < 127:
                strat_buf += chr(key)
            continue

        elif screen in (SCREEN_MODE_SELECT, SCREEN_API_INPUT) and api_editing:
            if   key == 27:
                api_editing = False; api_buf = ""
            elif key in (9,):
                fkey, _ = APIFIELDS[api_sel]
                setattr(state, fkey, api_buf.strip())
                api_sel = (api_sel + 1) % len(APIFIELDS)
                api_buf = str(getattr(state, APIFIELDS[api_sel][0], ""))
            elif key in (curses.KEY_ENTER, 10, 13):
                fkey, _ = APIFIELDS[api_sel]
                setattr(state, fkey, api_buf.strip())
                api_editing = False; api_buf = ""
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                api_buf = api_buf[:-1]
            elif 32 <= key < 127:
                ch = chr(key)
                if ch not in ('\n', '\r', '\t'):
                    api_buf += ch
            continue

        else:
            # Esc / B = back
            if key == 27 or key in (ord('b'), ord('B')):
                if screen_history:
                    go_back()
                    continue

            # F1-F5 global tab navigation
            if   key == curses.KEY_F1:  action = "DASHBOARD"
            elif key == curses.KEY_F2:  action = "RUNNING"
            elif key == curses.KEY_F3:  action = "STRATEGY"
            elif key == curses.KEY_F4:  action = "LOGS"
            elif key == curses.KEY_F5:  action = "MODE_SELECT"
            elif key == curses.KEY_F6:  action = "SYMBOLS"
            elif key == curses.KEY_F7:  action = "ALERTS"
            elif screen == SCREEN_UPDATE:
                if hasattr(state, "f8_mode") and state.f8_mode == "files":
                    rows = state.f8_file_rows if hasattr(state, "f8_file_rows") else []
                    if key == curses.KEY_UP:
                        state.f8_file_sel = max(0, state.f8_file_sel - 1)
                    elif key == curses.KEY_DOWN:
                        state.f8_file_sel = min(len(rows) - 1, state.f8_file_sel + 1) if rows else 0
                elif hasattr(state, "f8_mode") and state.f8_mode == "guide":
                    if key == curses.KEY_UP:
                        state.f8_guide_sel = max(0, state.f8_guide_sel - 1)
                    elif key == curses.KEY_DOWN:
                        state.f8_guide_sel = min(len(_GUIDE_ROWS) - 1, state.f8_guide_sel + 1) if _GUIDE_ROWS else 0
            elif key in (ord('c'), ord('C')) and screen == SCREEN_ALERTS:
                action = "ALERT_CLEAR" 

            elif key in (ord('q'), ord('Q')):
                if   screen == SCREEN_RUNNING:   action = "STOP"
                elif screen == SCREEN_API_INPUT: pass
                else: action = "EXIT"

            elif key in (ord('s'), ord('S')) and screen not in (SCREEN_STRATEGY, SCREEN_API_INPUT):
                action = "START"
            elif key in (ord('l'), ord('L')) and screen not in (SCREEN_API_INPUT,):
                action = "LOGS"
            elif key in (ord('r'), ord('R')) and screen not in (SCREEN_MODE_SELECT, SCREEN_API_INPUT):
                action = "RESTART"
            elif key in (ord('m'), ord('M')) and screen not in (SCREEN_API_INPUT,):
                action = "MENU"

            elif screen == SCREEN_MENU:
                from ui.menu_screen import MENU_ITEMS
                active_items = [item for item in MENU_ITEMS if item[1]]
                if key == curses.KEY_UP:
                    menu_sel   = (menu_sel - 1) % len(active_items)
                    menu_hover = -1
                elif key == curses.KEY_DOWN:
                    menu_sel   = (menu_sel + 1) % len(active_items)
                    menu_hover = -1
                elif key in (curses.KEY_ENTER, 10, 13):
                    action = active_items[menu_sel][1]

            elif screen == SCREEN_STRATEGY:
                if key == curses.KEY_UP:     strat_sel = max(0, strat_sel-1)
                elif key == curses.KEY_DOWN: strat_sel = min(len(FIELDS)-1, strat_sel+1)
                elif key in (curses.KEY_ENTER, 10, 13): action = f"FIELD_{strat_sel}"

            elif screen == SCREEN_SYMBOLS:
                from ui.symbols_screen import _ensure_state as _sym_ensure
                _sym_ensure(state)
                if state._sym_add_mode:
                    if key in (27,):        # ESC
                        state._sym_add_mode = False; state._sym_buf = ""
                    elif key in (curses.KEY_ENTER, 10, 13):
                        sym_new = state._sym_buf.strip().upper()
                        if sym_new and sym_new not in state.watchlist_order:
                            state.watchlist_order.append(sym_new)
                            state.watchlist.append({"symbol": sym_new, "price": 0.0,
                                "change_24h": 0.0, "high_24h": 0.0, "low_24h": 0.0, "volume": 0.0})
                        state._sym_add_mode = False; state._sym_buf = ""
                    elif key in (curses.KEY_BACKSPACE, 127):
                        state._sym_buf = state._sym_buf[:-1]
                    elif 32 <= key < 127:
                        state._sym_buf += chr(key)
                else:
                    if key == curses.KEY_UP:    state._sym_sel = max(0, state._sym_sel - 1)
                    elif key == curses.KEY_DOWN:
                        n = len(state.watchlist_order)
                        state._sym_sel = min(n-1, state._sym_sel + 1) if n else 0
                    elif key in (ord(' '),):    action = "SYM_TOGGLE_SEL"
                    elif key in (curses.KEY_ENTER, 10, 13): action = "SYM_TOGGLE_SEL"
                    elif key in (ord('a'), ord('A')): action = "SYM_ADD"
                    elif key in (ord('d'), ord('D')): action = "SYM_DEL" 

            elif screen == SCREEN_MODE_SELECT:
                if key in (curses.KEY_ENTER, 10, 13): action = "MODE_CONFIRM"
                elif key == ord('1'): action = "POS_ONE_WAY"
                elif key == ord('2'): action = "POS_HEDGE"
                elif key in (ord('d'), ord('D')): action = "MODE_DEMO"
                elif key in (ord('r'), ord('R')): action = "MODE_REAL"

            elif screen in (SCREEN_API_INPUT, SCREEN_MODE_SELECT):
                if key == curses.KEY_UP:     api_sel = max(0, api_sel-1)
                elif key == curses.KEY_DOWN: api_sel = min(len(APIFIELDS)-1, api_sel+1)
                elif key == ord('\t'):       api_sel = (api_sel + 1) % len(APIFIELDS)
                elif key in (curses.KEY_ENTER, 10, 13): action = f"APIFIELD_{api_sel}"

        if not action:
            continue

        # ── Safety gate: dangerous actions need a second press to confirm ──
        # "Dangerous" = anything that starts touching real money. First press
        # just arms it (button turns orange, label implies "press again");
        # the actual effect only runs on a second press within the window.
        is_dangerous = (
            (action == "MODE_CONFIRM" and mode_tmp == "real") or
            (action == "START" and state.mode == "real")
        )
        if is_dangerous:
            now = time.time()
            armed = (state.pending_confirm_action == action and
                      now < state.pending_confirm_until)
            if not armed:
                state.pending_confirm_action = action
                state.pending_confirm_until  = now + 2.5
                continue  # swallow this press — just arms the button
            else:
                state.pending_confirm_action = None
                state.pending_confirm_until  = 0.0
        else:
            # Any other action cancels a pending confirmation in progress
            state.pending_confirm_action = None
            state.pending_confirm_until  = 0.0

        # ── Click/press feedback: flash the button before executing ────────
        # Works the same for mouse clicks and keyboard Enter: look up the
        # (row, x1, x2) of whichever button matched this action, then
        # briefly invert its colors so the user sees instant confirmation.
        try:
            region = get_region_for_action(action)
            if region:
                ry, rx1, rx2 = region
                flash_region(stdscr, ry, rx1, rx2)
        except curses.error:
            pass

        # ── Action dispatch ───────────────────────────────────────────────────
        # ── Symbol watchlist actions ──────────────────────────────────────────────
        if action == "SYM_TOGGLE_SEL" or (action and action.startswith("SYM_TOGGLE_")):
            from ui.symbols_screen import _ensure_state as _sym_ensure
            _sym_ensure(state)
            if action == "SYM_TOGGLE_SEL":
                idx = state._sym_sel
            else:
                try:
                    idx = int(action.split("_")[-1])
                except Exception:
                    idx = state._sym_sel
            if state.watchlist_order and 0 <= idx < len(state.watchlist_order):
                sym = state.watchlist_order[idx]
                if sym in state.active_symbols:
                    state.active_symbols.discard(sym)
                else:
                    state.active_symbols.add(sym)
                state._sym_sel = idx
            continue

        if action == "SYM_ADD":
            from ui.symbols_screen import _ensure_state as _sym_ensure
            _sym_ensure(state)
            state._sym_add_mode = True
            state._sym_buf = ""
            continue

        if action == "SYM_DEL":
            from ui.symbols_screen import _ensure_state as _sym_ensure
            _sym_ensure(state)
            syms = state.watchlist_order
            sel2 = state._sym_sel
            if syms and 0 <= sel2 < len(syms):
                sym = syms.pop(sel2)
                state.active_symbols.discard(sym)
                state.watchlist = [d for d in state.watchlist if d.get('symbol') != sym]
                state._sym_sel  = max(0, sel2 - 1)
            continue

        if action == "SYM_ALL_ON":
            state.active_symbols = set(state.watchlist_order)
            continue

        if action == "SYM_ALL_OFF":
            state.active_symbols = set()
            continue

        if action == "SYM_SEARCH":
            state._sym_search_mode = not getattr(state, '_sym_search_mode', False)
            if not state._sym_search_mode:
                state._sym_search = ""
            continue

        # ── Alert actions ────────────────────────────────────────────────────
        if action == "ALERT_CLEAR":
            _ensure_alerts(state)
            state.alerts = []
            continue
        elif action and action.startswith("ALERT_FILTER_"):
            _ensure_alerts(state)
            state.alert_filter = action.split("ALERT_FILTER_")[1]
            continue
        elif action == "ALERT_TG_TOGGLE":
            _ensure_alerts(state)
            state.telegram_enabled = not getattr(state, 'telegram_enabled', False)
            continue
        elif action == "ALERT_EM_TOGGLE":
            _ensure_alerts(state)
            state.email_enabled = not getattr(state, 'email_enabled', False)
            continue
        elif action == "API_EM_TOGGLE":
            _ensure_api_state(state)
            state.email_enabled = not getattr(state, 'email_enabled', False)
            continue
        elif action == "API_EM_TEST":
            _ensure_api_state(state)
            if api_editing:
                fkey, _ = APIFIELDS[api_sel]
                setattr(state, fkey, api_buf.strip())
                api_editing = False
                api_buf = ""
            if not email_testing:
                email_testing  = True
                email_status   = ""
                email_status_ok = False
                email_test_res = {}
                t = threading.Thread(
                    target=_do_email_test,
                    args=(state, email_test_res),
                    daemon=True)
                t.start()
            else:
                push_alert(state, "ERR", "Email config incomplete — fill all SMTP fields first")
        elif action == "ALERT_TEST_OK":
            push_alert(state, "OK",   "BTC/USDT BUY filled @ market · TP: +2.0%")
            continue
        elif action == "ALERT_TEST_WARN":
            push_alert(state, "WARN", "Daily trade limit gần đạt: 4/5 trades")
            continue
        elif action == "ALERT_TEST_ERR":
            push_alert(state, "ERR",  "API rate limit hit — retry sau 2s")
            continue
        elif action == "ALERT_TEST_INFO":
            push_alert(state, "INFO", "Bot restart thành công · uptime reset")
            continue
        elif action and action.startswith("AUTOPAUSE_"):
            _ensure_alerts(state)
            attr_name = action.split("AUTOPAUSE_")[1].lower()
            cur = getattr(state, attr_name, False)
            setattr(state, attr_name, not cur)
            continue

        # ── Theme switcher ──────────────────────────────────────────────
        if action and action.startswith("THEME_"):
            theme_name = action.split("THEME_")[1].lower()
            set_theme(theme_name)
            continue

        # ── Watchlist sort ──────────────────────────────────────────────────
        if action and action.startswith("WL_SORT_"):
            from ui.dashboard import _wl_sort
            sk = action.split("WL_SORT_")[1].lower()
            _wl_sort[0] = sk
            continue

        # ── Auto-pause toggle (from strategy screen) ───────────────────────
        if action and action.startswith("AUTOPAUSE_") and "AUTOPAUSE_AUTOPAUSE" not in action:
            _ensure_alerts(state)
            attr_name = action.split("AUTOPAUSE_")[1].lower()
            cur = getattr(state, attr_name, False)
            setattr(state, attr_name, not cur)
            continue

        if   action == "EXIT":   break
        elif action == "BACK":
            if screen == SCREEN_UPDATE:
                state.f8_mode = "update"
            else:
                go_back()

        elif action == "UPDATE":
            go_to(SCREEN_UPDATE)

        elif action == "UPDATE_SCAN":
            from updates.update import check_update_async
            check_update_async()
            go_to(SCREEN_UPDATE)

        elif action == "UPDATE_INSTALL":
            from updates.update import install_update_async
            install_update_async()

        elif action == "UPDATE_ROLLBACK":
            from updates.update import rollback_async
            rollback_async()

        elif action == "UPDATE_FILELIST":
            state.f8_mode = "files"
            state.f8_file_rows = []
            go_to(SCREEN_UPDATE)

        elif action == "UPDATE_FILE_REFRESH":
            state.f8_mode = "files"
            state.f8_file_rows = []
            state.f8_file_scroll = 0
            state.f8_file_sel = 0
            go_to(SCREEN_UPDATE)

        elif action == "UPDATE_SWITCH_UPDATE":
            state.f8_mode = "update"
            go_to(SCREEN_UPDATE)

        elif action == "UPDATE_GUIDE":
            state.f8_mode = "guide"
            state.f8_guide_scroll = 0
            go_to(SCREEN_UPDATE)

        elif action == "UPDATE_SWITCH_GUIDE":
            state.f8_mode = "guide"
            state.f8_guide_scroll = 0
            go_to(SCREEN_UPDATE)

        elif action == "MENU":
            screen_history.clear()
            screen    = SCREEN_MENU
            menu_sel  = 0
            menu_hover = -1
            if strat_editing: strat_editing = False
            if api_editing:   api_editing   = False

        elif action == "DASHBOARD":
            go_to(SCREEN_DASHBOARD)
            load_accounts(cfg)
        elif action == "SYMBOLS":    go_to(SCREEN_SYMBOLS)
        elif action == "ALERTS":     go_to(SCREEN_ALERTS)
        elif action == "LOGS":      go_to(SCREEN_LOGS)
        elif action == "STRATEGY":  go_to(SCREEN_STRATEGY)
        elif action == "RUNNING":
            go_to(SCREEN_RUNNING if state.running else SCREEN_DASHBOARD)
        elif action == "MODE_SELECT":
            mode_tmp     = state.mode
            pos_mode_tmp = getattr(state, 'position_mode', 'one-way')
            go_to(SCREEN_MODE_SELECT)

        elif action == "MODE_DEMO":   mode_tmp = "demo"
        elif action == "MODE_REAL":   mode_tmp = "real"
        elif action == "POS_ONE_WAY": pos_mode_tmp = "one-way"
        elif action == "POS_HEDGE":   pos_mode_tmp = "hedge"
        elif action == "MODE_CONFIRM":
            state.mode          = mode_tmp
            cfg["mode"]         = mode_tmp
            state.position_mode = pos_mode_tmp
            cfg["position_mode"] = pos_mode_tmp
            save_config(cfg)
            state.add_log(f"Mode {mode_tmp.upper()} selected.")
            if mode_tmp == "demo":
                from ui.symbols_screen import _ensure_state as _sym_ensure
                _sym_ensure(state)
                start_watchlist_fetcher(state)
            if pos_mode_tmp == "hedge":
                state.add_log("Switched to Hedge Mode. Enable Hedge Mode on Bybit first.", "WARN")
            go_to(SCREEN_DASHBOARD)

        elif action == "API_SETTINGS":
            api_sel     = 0
            api_editing = False
            api_buf     = ""
            api_status  = ""
            api_testing = False
            email_status  = ""
            email_status_ok = False
            email_test_res = {}
            go_to(SCREEN_MODE_SELECT)  # combined Mode & API screen

        elif action.startswith("APIFIELD_"):
            idx         = int(action.split("_")[1])
            api_sel     = idx
            api_editing = True
            api_buf     = str(getattr(state, APIFIELDS[idx][0], ""))
        elif action == "API_TEST":
            if api_editing:
                fkey, _ = APIFIELDS[api_sel]
                setattr(state, fkey, api_buf.strip())
                api_editing = False
                api_buf = ""
            if not api_testing:
                api_testing  = True
                api_status   = ""
                api_test_res = {}
                t = threading.Thread(
                    target=_do_api_test,
                    args=(state.bybit_api_key, state.bybit_api_secret,
                          api_test_res, state.mode == "demo"),
                    daemon=True)
                t.start()
        elif action == "API_SAVE":
            _ensure_api_state(state)
            if api_editing:
                fkey, _ = APIFIELDS[api_sel]
                setattr(state, fkey, api_buf.strip())
                api_editing = False
                api_buf = ""
            cfg["bybit_api_key"]      = state.bybit_api_key
            cfg["bybit_api_secret"]   = state.bybit_api_secret
            cfg["telegram_bot_token"] = getattr(state, 'telegram_bot_token', '')
            cfg["telegram_chat_id"]   = getattr(state, 'telegram_chat_id', '')
            cfg["sendgrid_api_key"]   = getattr(state, 'sendgrid_api_key', '')
            cfg["email_from"]         = getattr(state, 'email_from', '')
            save_config(cfg)
            key_short = state.bybit_api_key[:6] + "..." if state.bybit_api_key else "N/A"
            state.add_log(f"API key saved ({key_short}).")
            load_accounts(cfg)
            go_to(SCREEN_DASHBOARD)

        elif action == "START":
            start_bot()
            push_alert(state, "OK", f"Bot started · mode {state.mode.upper()} · {state.pair}")
            go_to(SCREEN_RUNNING)
        elif action == "STOP":
            stop_bot()
            push_alert(state, "WARN", "Bot stopped manually")
            go_to(SCREEN_DASHBOARD)
        elif action == "RESTART":
            stop_bot(); time.sleep(0.2); start_bot(); go_to(SCREEN_RUNNING)

        elif action == "LOG_UP":     log_scroll += 3
        elif action == "LOG_DOWN":   log_scroll  = max(0, log_scroll-3)
        elif action == "LOG_BOTTOM": log_scroll  = 0

        elif action == "STRAT_SAVE":
            for fkey, _, ftype in FIELDS:
                cfg.setdefault("strategy", {})[fkey] = getattr(state, fkey)
            save_config(cfg); state.add_log("Strategy config saved.")
        elif action == "STRAT_RESET":
            apply_config_to_state(cfg, state); state.add_log("Strategy config reset.")
        elif action and action.startswith("FIELD_"):
            idx           = int(action.split("_")[1])
            strat_sel     = idx
            strat_editing = True
            strat_buf     = str(getattr(state, FIELDS[idx][0], ""))

    stop_bot()
    stop_watchlist_fetcher()

def run():
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run()
