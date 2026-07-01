"""
F6 Symbols — tick/untick which symbols appear in the Watchlist on the Overview tab.

Symbols carry live-ish data that the engine should populate (price, change, etc.)
into state.watchlist.  This screen manages state.active_symbols (a set) and the
ordered list state.watchlist_order (list of symbol strings).

Keys:
  ↑/↓        navigate
  SPACE/Enter toggle active flag
  A          add a custom symbol (opens tiny prompt)
  D          delete selected symbol from list
  ESC/B      back to Overview
"""

import curses
import time

from .base import draw_box, safe_addstr, draw_btn, reg, clear_clicks, get_version, draw_header
from .colors import cg, GREEN, RED, YELLOW, CYAN, WHITE, DIM

import threading
import time as _time

# ── Price history + RSI cache (shared with dashboard.py pattern) ──────────────
_sym_price_hist: dict = {}
_sym_rsi_cache:  dict = {}

def _rsi_from_prices(prices, period=14):
    if len(prices) < period + 1:
        return None
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains  = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]
    avg_g  = sum(gains[:period]) / period
    avg_l  = sum(losses[:period]) / period
    for i in range(period, len(deltas)):
        avg_g = (avg_g * (period - 1) + gains[i])  / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    return 100 - (100 / (1 + avg_g / avg_l))

def _update_price_hist(sym, price):
    if price <= 0:
        return
    hist = _sym_price_hist.setdefault(sym, [])
    if not hist or hist[-1] != price:
        hist.append(price)
    if len(hist) > 60:
        _sym_price_hist[sym] = hist[-60:]
    rsi = _rsi_from_prices(hist)
    if rsi is not None:
        _sym_rsi_cache[sym] = rsi

def _spark(vals, w=10):
    if not vals or w <= 0:
        return "─" * w
    blocks = " ▁▂▃▄▅▆▇█"
    mn, mx = min(vals), max(vals)
    rng    = mx - mn or 1
    sample = vals[::max(1, len(vals) // w)][-w:]
    return "".join(blocks[int((v - mn) / rng * 8)] for v in sample).ljust(w)

def _trend_arrow(chg):
    if chg > 2:      return "↑↑"
    if chg > 0.5:    return "↑"
    if chg > -0.5:   return "→"
    if chg > -2:     return "↓"
    return "↓↓"

def _fmt_price(p):
    if p == 0:   return "0.00"
    if p >= 1e4: return f"{p:.1f}"
    if p >= 100: return f"{p:.2f}"
    if p >= 1:   return f"{p:.3f}"
    return f"{p:.4f}"

# ── Background price fetcher ──────────────────────────────────────────────────
_fetch_thread = None
_fetch_stop   = threading.Event()

def _fetch_loop(state):
    from bot.bybit_api import get_ticker
    while not _fetch_stop.is_set():
        connected = getattr(state, 'bybit_connected', False) or getattr(state, 'mode', '') == 'demo'
        if connected:
            for sym in list(getattr(state, 'watchlist_order', [])):
                if _fetch_stop.is_set():
                    break
                bybit_sym = sym.replace('/', '')
                try:
                    ticker = get_ticker(bybit_sym, demo=(getattr(state, 'mode', 'demo') == 'demo'))
                    for entry in state.watchlist:
                        if entry.get('symbol') == sym:
                            entry['price']      = ticker.get('price', 0.0)
                            entry['change_24h'] = ticker.get('change24h', 0.0)
                            entry['high_24h']   = ticker.get('high24h', 0.0)
                            entry['low_24h']    = ticker.get('low24h', 0.0)
                            entry['volume']     = ticker.get('volume', 0.0)
                            _update_price_hist(sym, entry['price'])
                            break
                except Exception:
                    pass
                _fetch_stop.wait(0.3)
        _fetch_stop.wait(10)


def start_watchlist_fetcher(state):
    global _fetch_thread, _fetch_stop
    if _fetch_thread and _fetch_thread.is_alive():
        return
    _fetch_stop.clear()
    _fetch_thread = threading.Thread(target=_fetch_loop, args=(state,), daemon=True)
    _fetch_thread.start()


def stop_watchlist_fetcher():
    global _fetch_stop
    _fetch_stop.set()


# Default universe of tradable symbols shown on first launch
DEFAULT_SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "DOGE/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "DOT/USDT",
    "LINK/USDT",
    "MATIC/USDT",
    "LTC/USDT",
    "UNI/USDT",
    "ATOM/USDT",
    "FIL/USDT",
    "NEAR/USDT",
    "APT/USDT",
    "ARB/USDT",
    "OP/USDT",
    "SUI/USDT",
]


def _ensure_state(state):
    """Initialise symbol-related state fields if not already present."""
    # Use 'not X' to catch both None AND empty list/set (state.py inits them as [] / set())
    if not state.watchlist_order:
        state.watchlist_order = list(DEFAULT_SYMBOLS)
    if not state.active_symbols:
        state.active_symbols = {"BTC/USDT", "ETH/USDT"}
    # Sync watchlist entries with watchlist_order (add missing, keep existing data)
    existing = {d['symbol'] for d in state.watchlist}
    for sym in state.watchlist_order:
        if sym not in existing:
            state.watchlist.append({"symbol": sym, "price": 0.0, "change_24h": 0.0,
                                     "high_24h": 0.0, "low_24h": 0.0, "volume": 0.0})
    if not hasattr(state, '_sym_sel'):
        state._sym_sel = 0
    if not hasattr(state, '_sym_add_mode'):
        state._sym_add_mode = False
    if not hasattr(state, '_sym_buf'):
        state._sym_buf = ""


def draw_symbols(win, state):
    _ensure_state(state)
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()

    draw_header(win, max_x, "SYMBOLS", state)

    y0    = 3
    syms  = state.watchlist_order
    sel   = state._sym_sel
    if syms:
        state._sym_sel = sel = max(0, min(sel, len(syms) - 1))

    connected = state.bybit_connected or state.mode == "demo"
    list_h = max_y - y0 - 5

    # ── Left panel: symbol list ────────────────────────────────────────────────
    lw   = 30
    draw_box(win, y0, 0, list_h, lw, "SYMBOL LIST", GREEN)

    # Search bar row
    search_query = getattr(state, '_sym_search', "")
    search_lbl = f" Search: {search_query}_" if getattr(state, '_sym_search_mode', False) else f" Search: {search_query} "
    safe_addstr(win, y0+1, 1, search_lbl[:lw-3], cg(YELLOW if getattr(state,'_sym_search_mode',False) else DIM))
    reg(y0+1, 1, lw-2, "SYM_SEARCH")
    if search_query:
        syms = [s for s in syms if search_query.lower() in s.lower()]

    visible = list_h - 3
    scroll  = max(0, sel - visible + 1)

    if not connected:
        safe_addstr(win, y0 + 3, 2, "No API connection.", cg(RED) | curses.A_BOLD)
        safe_addstr(win, y0 + 4, 2, "Go to F5 Mode/API", cg(YELLOW))
        safe_addstr(win, y0 + 5, 2, "to enter & test", cg(YELLOW))
        safe_addstr(win, y0 + 6, 2, "your API key first.", cg(YELLOW))
    else:
        for i, sym in enumerate(syms[scroll: scroll + visible]):
            real_i = i + scroll
            y = y0 + 2 + i
            is_sel    = (real_i == sel)
            is_active = sym in state.active_symbols

            sym_data = next((d for d in state.watchlist if d.get('symbol') == sym), {})
            price  = sym_data.get('price', 0.0)
            chg    = sym_data.get('change_24h', 0.0)
            chg_c  = GREEN if chg >= 0 else RED
            arrow  = _trend_arrow(chg)

            tick = "✔" if is_active else "○"
            item = f" {tick} {arrow} {sym:<8}"
            if is_sel:
                attr = cg(CYAN) | curses.A_BOLD | curses.A_REVERSE
            elif is_active:
                attr = cg(GREEN)
            else:
                attr = cg(DIM)
            safe_addstr(win, y, 1, item[:lw-12], attr)

            chg_s = f"{'+' if chg>=0 else ''}{chg:.1f}%"
            safe_addstr(win, y, lw-10, chg_s[:9], cg(chg_c) | (curses.A_BOLD if is_sel else 0))
            reg(y, 1, lw - 2, f"SYM_TOGGLE_{real_i}")

        if len(syms) > visible:
            safe_addstr(win, y0 + list_h - 1, 2,
                f"↑↓ scroll  {scroll+1}-{min(scroll+visible,len(syms))}/{len(syms)}", cg(DIM))

    # ── Right panel: selected symbol detail ────────────────────────────────────
    rw  = max_x - lw
    rh1 = 10
    draw_box(win, y0, lw, rh1, rw, "SYMBOL DETAIL", CYAN)

    if not connected:
        safe_addstr(win, y0+2, lw+2, "Connect API to view", cg(DIM))
        safe_addstr(win, y0+3, lw+2, "live market data.",   cg(DIM))
    elif syms and 0 <= sel < len(syms):
        cur_sym = syms[sel]
        sym_data = next((d for d in state.watchlist if d.get('symbol') == cur_sym), {})
        price  = sym_data.get('price', 0.0)
        chg    = sym_data.get('change_24h', 0.0)
        high   = sym_data.get('high_24h', 0.0)
        low    = sym_data.get('low_24h', 0.0)
        vol    = sym_data.get('volume', 0.0)
        is_active = cur_sym in state.active_symbols
        rsi   = _sym_rsi_cache.get(cur_sym)

        chg_c  = GREEN if chg >= 0 else RED
        arrow  = _trend_arrow(chg)
        phist  = _sym_price_hist.get(cur_sym, [])

        safe_addstr(win, y0+1, lw+2, f"{cur_sym}", cg(CYAN) | curses.A_BOLD)
        active_tag = "● ON" if is_active else "○ OFF"
        safe_addstr(win, y0+1, lw+16, active_tag, cg(GREEN if is_active else DIM))
        reg(y0+1, lw+16, lw+21, f"SYM_TOGGLE_{sel}")

        if price > 0:
            safe_addstr(win, y0+2, lw+2, f"Price:      {_fmt_price(price)} USDT", cg(WHITE))
            safe_addstr(win, y0+2, lw+2, f"Price:      ", cg(WHITE))
            safe_addstr(win, y0+2, lw+14, f"{_fmt_price(price)} USDT", cg(GREEN))
            chg_str = f"{arrow} {'+' if chg>=0 else ''}{chg:.2f}%"
            safe_addstr(win, y0+3, lw+2, f"Change:     ", cg(WHITE))
            safe_addstr(win, y0+3, lw+14, chg_str, cg(chg_c) | curses.A_BOLD)
            safe_addstr(win, y0+4, lw+2, f"High/Low:   ", cg(WHITE))
            safe_addstr(win, y0+4, lw+14, f"{_fmt_price(high)} / {_fmt_price(low)}", cg(CYAN))
            vol_s = f"{vol:.1f}K" if vol > 0 else "—"
            safe_addstr(win, y0+5, lw+2, f"Volume:     ", cg(WHITE))
            safe_addstr(win, y0+5, lw+14, vol_s, cg(CYAN))
            rsi_s = f"{rsi:.1f}" if rsi is not None else "—"
            rsi_c = RED if rsi and rsi > 70 else GREEN if rsi and rsi < 30 else WHITE
            safe_addstr(win, y0+6, lw+2, f"RSI (14):   ", cg(WHITE))
            safe_addstr(win, y0+6, lw+14, rsi_s, cg(rsi_c) | curses.A_BOLD)
            spark_w = min(rw - 18, 28)
            safe_addstr(win, y0+7, lw+2, f"Trend:      ", cg(WHITE))
            safe_addstr(win, y0+7, lw+14, _spark(phist, w=spark_w), cg(chg_c))
            safe_addstr(win, y0+8, lw+2, f"Status:     ", cg(WHITE))
            safe_addstr(win, y0+8, lw+14, "● ACTIVE" if is_active else "○ Inactive", cg(GREEN if is_active else DIM))
        else:
            safe_addstr(win, y0+2, lw+2, "Price:      fetching...", cg(DIM))
            safe_addstr(win, y0+3, lw+2, "Status:     ", cg(WHITE))
            safe_addstr(win, y0+3, lw+14, "● ACTIVE" if is_active else "○ Inactive", cg(GREEN if is_active else DIM))

        # Toggle button in detail panel
        toggle_lbl = " [✖ Deactivate] " if is_active else " [✔ Activate] "
        toggle_col = RED if is_active else GREEN
        safe_addstr(win, y0+9, lw+2, toggle_lbl, cg(toggle_col) | curses.A_BOLD)
        reg(y0+9, lw+2, lw+2+len(toggle_lbl)-1, f"SYM_TOGGLE_{sel}")
    else:
        safe_addstr(win, y0+2, lw+2, "No symbol selected.", cg(DIM))

    # ── Active symbols summary ─────────────────────────────────────────────────
    rh2 = max_y - y0 - rh1 - 5
    if rh2 >= 4:
        draw_box(win, y0+rh1, lw, rh2, rw, "ACTIVE WATCHLIST", GREEN)
        if not connected:
            safe_addstr(win, y0+rh1+2, lw+2, "Connect API key to see live data.", cg(DIM))
        else:
            active_list = sorted(state.active_symbols)
            hdr2 = f"{'SYMBOL':<10} {'PRICE':>8} {'CHG%':>6} {'RSI':>5} SIGNAL"
            safe_addstr(win, y0+rh1+1, lw+2, hdr2, cg(WHITE) | curses.A_BOLD)
            for i, sym in enumerate(active_list[:rh2-3]):
                sym_data = next((d for d in state.watchlist if d.get('symbol') == sym), {})
                price  = sym_data.get('price', 0.0)
                chg    = sym_data.get('change_24h', 0.0)
                rsi    = _sym_rsi_cache.get(sym)
                chg_c  = GREEN if chg >= 0 else RED
                chg_s  = f"{'+' if chg>=0 else ''}{chg:.1f}%"
                price_s = f"{'—':>8}" if price <= 0 else f"{_fmt_price(price):>8}"
                rsi_s  = f"{rsi:.0f}" if rsi is not None else "—"
                rsi_c  = RED if rsi and rsi > 70 else GREEN if rsi and rsi < 30 else WHITE
                is_tp  = (sym == state.pair)
                sig    = state.signal if is_tp else "—"
                sig_c  = GREEN if sig == "BUY" else RED if sig == "SELL" else DIM
                safe_addstr(win, y0+rh1+2+i, lw+2,  f"{sym:<10}",  cg(CYAN))
                safe_addstr(win, y0+rh1+2+i, lw+12, price_s,        cg(GREEN if price > 0 else DIM))
                safe_addstr(win, y0+rh1+2+i, lw+21, f"{chg_s:>6}",  cg(chg_c))
                safe_addstr(win, y0+rh1+2+i, lw+28, rsi_s,           cg(rsi_c) | curses.A_BOLD)
                safe_addstr(win, y0+rh1+2+i, lw+34, f" {sig}",       cg(sig_c) | curses.A_BOLD)
            if not active_list:
                safe_addstr(win, y0+rh1+2, lw+2, "No active symbols. SPACE to activate.", cg(DIM))

    # ── Add symbol input box ───────────────────────────────────────────────────
    if state._sym_add_mode:
        ay = max_y - 5
        aw2 = 40
        ax  = (max_x - aw2) // 2
        draw_box(win, ay, ax, 3, aw2, "ADD SYMBOL (Enter=confirm  Esc=cancel)", YELLOW)
        safe_addstr(win, ay+1, ax+2, f"Symbol: {state._sym_buf}_", cg(YELLOW) | curses.A_BOLD)

    # ── Bottom buttons ─────────────────────────────────────────────────────────
    by = max_y - 3
    try:
        win.attron(cg(GREEN))
        win.addstr(by - 1, 0, "─" * max_x)
        win.attroff(cg(GREEN))
    except curses.error:
        pass
    bx = 2
    w = draw_btn(win, by, bx, "Space Toggle", "SYM_TOGGLE_SEL", color=GREEN); bx += w + 1
    w = draw_btn(win, by, bx, "A Add",        "SYM_ADD",        color=CYAN);  bx += w + 1
    w = draw_btn(win, by, bx, "D Delete",     "SYM_DEL",        color=RED);   bx += w + 1
    w = draw_btn(win, by, bx, "S All On",    "SYM_ALL_ON",     color=GREEN); bx += w + 1
    w = draw_btn(win, by, bx, "All Off",     "SYM_ALL_OFF",    color=DIM);   bx += w + 1
    w = draw_btn(win, by, bx, "◀ Overview",  "DASHBOARD",      color=WHITE); bx += w + 1
    draw_btn(win, by, bx, "✖ Quit", "EXIT", color=RED)

    safe_addstr(win, by+1, 2,
        "↑↓ nav  SPACE/Enter toggle active  A=add  D=del  S=select all  / search  B=back",
        cg(DIM))

    
    from .base import draw_theme_bar
    draw_theme_bar(win, max_y, max_x)
    win.refresh()
