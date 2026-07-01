import curses
import time
import os
import platform

from .base import draw_box, safe_addstr, draw_btn, reg, clear_clicks, get_version, heartbeat_on, step_toward, draw_theme_bar, THEME_LABELS, draw_header, draw_signal_badge_box, draw_sort_pill
from .colors import cg, GREEN, RED, YELLOW, CYAN, WHITE, DIM


def _get_cpu_pct():
    try:
        def _read():
            with open('/proc/stat') as f:
                parts = f.readline().split()
            idle  = int(parts[4])
            total = sum(int(x) for x in parts[1:])
            return idle, total
        i1, t1 = _read()
        time.sleep(0.05)
        i2, t2 = _read()
        diff_t = t2 - t1 or 1
        return 100.0 * (1 - (i2 - i1) / diff_t)
    except Exception:
        return 0.0

def _get_mem_info():
    try:
        info = {}
        with open('/proc/meminfo') as f:
            for line in f:
                key, val = line.split(':')
                info[key.strip()] = int(val.strip().split()[0]) * 1024
        total = info.get('MemTotal', 0)
        avail = info.get('MemAvailable', info.get('MemFree', 0))
        used  = total - avail
        pct   = (used / total * 100) if total > 0 else 0.0
        return used, total, pct
    except Exception:
        return 0, 0, 0.0

def _get_disk_info():
    try:
        st    = os.statvfs('/')
        total = st.f_blocks * st.f_frsize
        free  = st.f_bfree  * st.f_frsize
        used  = total - free
        pct   = (used / total * 100) if total > 0 else 0.0
        return used, total, pct
    except Exception:
        return 0, 0, 0.0

def _get_net_info():
    try:
        with open('/proc/net/dev') as f:
            lines = f.readlines()[2:]
        rx = tx = 0
        for line in lines:
            parts = line.split()
            if len(parts) > 9:
                rx += int(parts[1])
                tx += int(parts[9])
        return rx // 1024, tx // 1024
    except Exception:
        return 0, 0

def _sys_uptime():
    try:
        with open('/proc/uptime') as f:
            secs = int(float(f.read().split()[0]))
        h = secs // 3600; m = (secs % 3600) // 60; s = secs % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    except Exception:
        return "—"

def _cpu_temp():
    for path in ['/sys/class/thermal/thermal_zone0/temp',
                 '/sys/class/hwmon/hwmon0/temp1_input']:
        try:
            with open(path) as f:
                return f"{int(f.read()) / 1000:.0f}°C"
        except Exception:
            pass
    return "N/A"

def _load_avg():
    try:
        with open('/proc/loadavg') as f:
            parts = f.read().split()
        return parts[0], parts[1], parts[2]
    except Exception:
        return "—", "—", "—"

def _spark(vals, w=10):
    if not vals or w <= 0:
        return "─" * w
    blocks = " ▁▂▃▄▅▆▇█"
    mn, mx = min(vals), max(vals)
    rng    = mx - mn or 1
    sample = vals[::max(1, len(vals) // w)][-w:]
    result = "".join(blocks[int((v - mn) / rng * 8)] for v in sample)
    return result.ljust(w)

def _pct_bar(pct, w=10):
    filled = int(max(0, min(pct, 100)) / 100 * w)
    return "█" * filled + "░" * (w - filled)

def _fmt_vol(vol_k: float) -> str:
    if vol_k >= 1_000_000:
        return f"{vol_k/1_000_000:.1f}B"
    if vol_k >= 1_000:
        return f"{vol_k/1_000:.1f}M"
    return f"{vol_k:.1f}K"

def _fmt_price(price: float) -> str:
    if price == 0:
        return "0.00"
    if price >= 10000:
        return f"{price:.1f}"
    if price >= 100:
        return f"{price:.2f}"
    if price >= 1:
        return f"{price:.3f}"
    return f"{price:.4f}"

_cpu_hist:  list = []
_wl_sort: list = ['sym']
_mem_hist:  list = []
_NET_RX_PREV = [0]
_net_hist:  list = []
_sym_price_hist: dict = {}
_sym_rsi_cache:  dict = {}

def _update_sys_history():
    global _cpu_hist, _mem_hist, _net_hist
    cpu = _get_cpu_pct()
    _, _, mem_pct = _get_mem_info()
    rx_kb, _ = _get_net_info()
    delta_rx = max(0, rx_kb - _NET_RX_PREV[0])
    _NET_RX_PREV[0] = rx_kb
    for lst, val in ((_cpu_hist, cpu), (_mem_hist, mem_pct), (_net_hist, delta_rx)):
        lst.append(val)
        if len(lst) > 60:
            del lst[:-60]

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

def _update_sym_data(watchlist):
    for entry in watchlist:
        sym   = entry.get('symbol', '')
        price = entry.get('price', 0.0)
        if price > 0:
            hist = _sym_price_hist.setdefault(sym, [])
            if not hist or hist[-1] != price:
                hist.append(price)
            if len(hist) > 60:
                _sym_price_hist[sym] = hist[-60:]
            rsi = _rsi_from_prices(hist)
            if rsi is not None:
                _sym_rsi_cache[sym] = rsi

def _seed_trend_from_klines(sym, state):
    hist = _sym_price_hist.get(sym, [])
    if len(hist) >= 3:
        return
    try:
        from bot.bybit_api import get_klines
        bybit_sym = sym.replace('/', '')
        demo      = getattr(state, 'mode', 'demo') == 'demo'
        klines    = get_klines(bybit_sym, interval='15', limit=20, demo=demo)
        prices    = [k['close'] for k in klines if k.get('close', 0) > 0]
        if prices:
            _sym_price_hist[sym] = prices[-30:]
            rsi = _rsi_from_prices(prices)
            if rsi is not None:
                _sym_rsi_cache[sym] = rsi
    except Exception:
        pass

def _win_stats(state):
    trades = getattr(state, 'recent_trades', [])
    if not trades:
        return "—", "—"
    wins  = sum(1 for t in trades if t.get('pnl_usdt', 0) > 0)
    total = len(trades)
    avg_r = sum(t.get('pnl_usdt', 0) for t in trades) / total
    return f"{wins/total*100:.0f}%", f"{'+' if avg_r >= 0 else ''}{avg_r:.2f}"

def _draw_watchlist(win, state, box_y, box_h, max_x):
    watchlist   = getattr(state, 'watchlist', [])
    active_syms = getattr(state, 'active_symbols', set())
    connected   = state.bybit_connected or state.mode == "demo"

    draw_box(win, box_y, 0, box_h, max_x, "SYMBOL WATCHLIST  [F6 edit]  [TAB sort]", GREEN)

    if not connected:
        safe_addstr(win, box_y+2, 2, "Connect API key first (F5 Mode/API) to see live data.", cg(YELLOW))
        return

    watchlist = [d for d in watchlist if d.get('symbol') in active_syms]

    sort_keys = [("sym","SYMBOL"), ("chg","CHG%"), ("vol","VOL"), ("rsi","RSI")]
    sx = 2; sy = box_y + 1
    for sk, sl in sort_keys:
        is_sel = (_wl_sort[0] == sk)
        w = draw_sort_pill(win, sy, sx, sl, is_sel, f"WL_SORT_{sk.upper()}")
        sx += w + 2
    safe_addstr(win, sy, sx+2, "[TAB to sort]", cg(DIM))

    if not watchlist:
        safe_addstr(win, box_y+2, 2, "No active symbols. Press F6 → SPACE to activate.", cg(DIM))
        return

    def _sort_key(d):
        sk = _wl_sort[0]
        if sk == 'chg': return d.get('change_24h', 0)
        if sk == 'vol': return d.get('volume', 0)
        if sk == 'rsi':
            r = _sym_rsi_cache.get(d.get('symbol',''), 50)
            return r if r else 50
        return d.get('symbol','')
    watchlist = sorted(watchlist, key=_sort_key, reverse=(_wl_sort[0] != 'sym'))

    COLS = [
        ("SYMBOL",  10, 10, 'l'),
        ("PRICE",    8, 10, 'r'),
        ("CHG%",     6,  7, 'r'),
        ("HIGH",     8, 10, 'r'),
        ("LOW",      8, 10, 'r'),
        ("VOL",      5,  6, 'r'),
        ("TREND",    8, 10, 'l'),
        ("RSI",      4,  5, 'r'),
        ("SIG",      4,  6, 'r'),
        ("STATUS",   6,  8, 'l'),
    ]

    avail = max_x - 2
    n_cols   = len(COLS)
    sep_total = n_cols - 1
    ideal_total = sum(c[2] for c in COLS) + sep_total

    if ideal_total <= avail:
        extra = avail - ideal_total
        widths = [c[2] for c in COLS]
        widths[6] += min(extra, 6)
        extra -= min(extra, 6)
        widths[1] += extra
    else:
        widths = [c[1] for c in COLS]
        spare  = avail - sum(widths) - sep_total
        growable = [6, 1, 3, 4]
        for idx in growable:
            if spare <= 0:
                break
            grow = min(COLS[idx][2] - widths[idx], spare)
            widths[idx] += grow
            spare -= grow

    xs = []
    x  = 1
    for w in widths:
        xs.append(x)
        x += w + 1

    hy = box_y + 1
    for i, ((hdr, *_), w, ox) in enumerate(zip(COLS, widths, xs)):
        if ox + w > max_x - 1:
            break
        h_txt = hdr[:w]
        safe_addstr(win, hy, ox, f"{h_txt:>{w}}" if COLS[i][3] == 'r' else f"{h_txt:<{w}}",
                    cg(WHITE) | curses.A_BOLD)

    max_rows = box_h - 3
    for ri, sym_data in enumerate(watchlist[:max_rows]):
        ry = box_y + 2 + ri
        if ry >= box_y + box_h - 1:
            break

        sym       = sym_data.get('symbol', '—')
        price     = sym_data.get('price', 0.0)
        chg       = sym_data.get('change_24h', 0.0)
        high      = sym_data.get('high_24h', 0.0)
        low       = sym_data.get('low_24h', 0.0)
        vol       = sym_data.get('volume', 0.0)
        is_active = sym in active_syms

        _seed_trend_from_klines(sym, state)

        phist   = _sym_price_hist.get(sym, [])
        trend_w = widths[6]
        trend_s = _spark(phist, w=trend_w) if len(phist) >= 2 else "─" * trend_w

        rsi_val = _sym_rsi_cache.get(sym)
        rsi_s   = f"{rsi_val:.0f}" if rsi_val is not None else "─"

        if sym == state.pair and state.signal != "NONE":
            sig_s   = state.signal
            sig_col = GREEN if state.signal == "BUY" else RED
        else:
            sig_s   = "─"
            sig_col = DIM

        status_s = "● ACTIVE" if is_active else "○ watch"

        chg_col   = GREEN if chg >= 0 else RED
        trend_col = GREEN if (len(phist) >= 2 and phist[-1] >= phist[0]) else RED
        rsi_col   = (RED if rsi_val and rsi_val > 70
                     else GREEN if rsi_val and rsi_val < 30
                     else WHITE) if rsi_val else DIM
        st_col    = GREEN if is_active else DIM
        sym_attr  = cg(CYAN) | (curses.A_BOLD if is_active else 0)

        values = [
            (sym[:widths[0]],                  'l', sym_attr),
            (_fmt_price(price),                'r', cg(GREEN)),
            (f"{'+' if chg>=0 else ''}{chg:.2f}%", 'r', cg(chg_col)),
            (_fmt_price(high),                 'r', cg(WHITE)),
            (_fmt_price(low),                  'r', cg(WHITE)),
            (_fmt_vol(vol),                    'r', cg(DIM)),
            (trend_s,                          'l', cg(trend_col)),
            (rsi_s,                            'r', cg(rsi_col)),
            (sig_s,                            'r', cg(sig_col) | curses.A_BOLD),
            (status_s,                         'l', cg(st_col)),
        ]

        for i, (val, align, attr) in enumerate(values):
            ox = xs[i]
            w  = widths[i]
            if ox + w > max_x - 1:
                break
            txt = val[:w]
            cell = f"{txt:>{w}}" if align == 'r' else f"{txt:<{w}}"
            safe_addstr(win, ry, ox, cell, attr)


def draw_dashboard(win, state):
    from .symbols_screen import _ensure_state as _sym_ensure
    _sym_ensure(state)
    _update_sys_history()
    _update_sym_data(getattr(state, 'watchlist', []))
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()

    draw_header(win, max_x, "DASHBOARD", state)

    y0 = 3

    paused = False
    if getattr(state, 'autopause_daily_loss', False):
        daily_loss_pct = abs(getattr(state,'daily_pnl',0)) / max(getattr(state,'equity',1),1) * 100
        if daily_loss_pct >= getattr(state,'max_daily_loss',5.0):
            paused = True
    if getattr(state, 'autopause_consec_loss', False):
        if getattr(state,'consecutive_losses',0) >= getattr(state,'max_consecutive_losses',3):
            paused = True
    if paused and state.running:
        safe_addstr(win, y0-1, 0, "─"*max_x, cg(RED))
        safe_addstr(win, y0-1, 2,
            " ⚠ AUTO-PAUSE ACTIVE — Daily PnL đạt ngưỡng · Bot tạm dừng lệnh mới [R to resume] ",
            cg(RED) | curses.A_BOLD)
        y0 += 1

    mem_used, mem_total, mem_pct = _get_mem_info()
    disk_used, disk_total, disk_pct = _get_disk_info()
    cpu_pct    = _cpu_hist[-1] if _cpu_hist else 0.0
    la1, la5, la15 = _load_avg()
    uptime_sys = _sys_uptime()
    cpu_temp   = _cpu_temp()
    try:
        cpu_count = os.cpu_count() or 1
    except Exception:
        cpu_count = 1

    c1 = max_x // 3
    c2 = max_x // 3
    c3 = max_x - c1 - c2
    bh = 14

    draw_box(win, y0, 0, bh, c1, "SYSTEM", GREEN)
    bar_w = max(6, c1 - 9)
    ind   = 7

    cpu_col = RED if cpu_pct > 85 else YELLOW if cpu_pct > 60 else GREEN
    safe_addstr(win, y0+1,  2, "CPU: ", cg(WHITE))
    safe_addstr(win, y0+1,  7, f"{cpu_pct:5.1f}%", cg(cpu_col))
    safe_addstr(win, y0+2, ind, _pct_bar(cpu_pct, bar_w), cg(cpu_col))

    mem_col = RED if mem_pct > 85 else YELLOW if mem_pct > 65 else GREEN
    safe_addstr(win, y0+3,  2, "RAM: ", cg(WHITE))
    safe_addstr(win, y0+3,  7, f"{mem_used/1e9:.1f}G/{mem_total/1e9:.1f}G", cg(mem_col))
    safe_addstr(win, y0+4, ind, _pct_bar(mem_pct, bar_w), cg(mem_col))

    disk_col = RED if disk_pct > 90 else YELLOW if disk_pct > 70 else GREEN
    safe_addstr(win, y0+5,  2, "DISK: ", cg(WHITE))
    safe_addstr(win, y0+5,  7, f"{disk_used/1e9:.0f}G/{disk_total/1e9:.0f}G", cg(disk_col))
    safe_addstr(win, y0+6, ind, _pct_bar(disk_pct, bar_w), cg(disk_col))

    net_delta = _net_hist[-1] if _net_hist else 0
    safe_addstr(win, y0+7,  2, "NET: ", cg(WHITE))
    safe_addstr(win, y0+7,  7, f"↓{net_delta:.0f}KB/s", cg(CYAN))
    safe_addstr(win, y0+8, ind, _spark(_net_hist, w=bar_w), cg(CYAN))

    safe_addstr(win, y0+9,  2, "LOAD:", cg(WHITE))
    safe_addstr(win, y0+9,  8, f"{la1} {la5} {la15} ({cpu_count}C)", cg(CYAN))
    safe_addstr(win, y0+10, 2, "TEMP:", cg(WHITE))
    safe_addstr(win, y0+10, 8, cpu_temp, cg(YELLOW))
    safe_addstr(win, y0+11, 2, "UPT: ", cg(WHITE))
    safe_addstr(win, y0+11, 8, uptime_sys, cg(GREEN))
    safe_addstr(win, y0+12, 2, "OS:  ", cg(WHITE))
    try:
        node = platform.node()[:c1-10] or "—"
    except Exception:
        node = "—"
    safe_addstr(win, y0+12, 8, node, cg(DIM))

    draw_box(win, y0, c1, bh, c2, "BOT STATUS", GREEN)
    sc = GREEN if state.status == "RUNNING" else RED
    status_attr = cg(sc) | curses.A_BOLD
    if state.status == "RUNNING" and not heartbeat_on():
        status_attr = cg(sc)

    daily_trades = getattr(state, 'daily_trades', 0)
    max_dt       = getattr(state, 'max_daily_trades', 5)

    lbl_x = c1 + 2
    val_x = c1 + 11
    pos_mode_disp = "ONE-WAY" if getattr(state, 'position_mode', 'one-way') == 'one-way' else "HEDGE"
    bot_rows = [
        ("STATUS:",    state.status,                                        sc,     status_attr),
        ("STRATEGY:",  state.strategy,                                      CYAN,   None),
        ("PAIR:",      f"{state.pair}  {state.timeframe}",                 CYAN,   None),
        ("RISK MODE:", state.risk_mode,                                     YELLOW, None),
        ("LEVERAGE:",  f"{state.leverage}x",                               YELLOW, None),
        ("POS MODE:",  pos_mode_disp,                                       CYAN,   None),
        ("TP / SL:",   f"{state.take_profit}%/{state.stop_loss}%",         GREEN,  None),
        ("MAX POS:",   str(state.max_positions),                            WHITE,  None),
        ("UPTIME:",    state.get_uptime_str(),                              GREEN,  None),
        ("TRADES:",    f"{daily_trades} / {max_dt} today",                 WHITE,  None),
    ]
    for i, (k, v, c, custom_attr) in enumerate(bot_rows[:bh-2]):
        safe_addstr(win, y0+1+i, lbl_x, k, cg(WHITE))
        attr = custom_attr if custom_attr is not None else cg(c)
        safe_addstr(win, y0+1+i, val_x, str(v)[:c2-10], attr)

    draw_box(win, y0, c1+c2, bh, c3, "PNL — TODAY", GREEN)

    state.pnl_display = step_toward(
        state.pnl_display, state.pnl_usdt,
        max_step=max(0.3, abs(state.pnl_usdt - state.pnl_display) * 0.3))

    px  = c1+c2+2
    pw  = c3 - 4
    pc  = GREEN if state.pnl_usdt >= 0 else RED
    sg  = "+" if state.pnl_display >= 0 else ""
    sig_col = GREEN if state.signal == "BUY" else RED if state.signal == "SELL" else YELLOW
    win_pct, avg_r = _win_stats(state)

    pnl_str = f"{sg}{state.pnl_display:.2f} USDT"
    safe_addstr(win, y0+1, px, pnl_str[:pw], cg(pc) | curses.A_BOLD)
    safe_addstr(win, y0+2, px, f"{sg}{state.pnl_pct:.2f}%"[:pw], cg(pc))
    safe_addstr(win, y0+3, px, _spark(state.pnl_history, w=pw), cg(pc))

    safe_addstr(win, y0+5, px, f"SIG:", cg(DIM))
    draw_signal_badge_box(win, y0+5, px+5, state.signal, state.score)

    rows_pnl = [
        (y0+8,  f"DAL:   {state.daily_pnl:+.2f}",  cg(GREEN if state.daily_pnl >= 0 else RED)),
        (y0+9,  f"TRDS:  {daily_trades}/{max_dt}",  cg(WHITE)),
        (y0+10, f"WIN%:  {win_pct}",                cg(GREEN if win_pct != '—' else DIM)),
        (y0+11, f"AVG R: {avg_r}",                  cg(GREEN if avg_r not in ('—',) and not str(avg_r).startswith('-') else (DIM if avg_r == '—' else RED))),
    ]
    for ry, txt, attr in rows_pnl:
        safe_addstr(win, ry, px, txt[:pw], attr)

    pnl_bar_pct = min(100, max(0, state.pnl_pct + 50))
    safe_addstr(win, y0+12, px, _pct_bar(pnl_bar_pct, pw), cg(pc))

    r2y = y0 + bh
    r2h = 7
    aw  = c1 + c2
    draw_box(win, r2y, 0,  r2h, aw,       "ACCOUNT",         GREEN)
    draw_box(win, r2y, aw, r2h, max_x-aw, "MARKET OVERVIEW", CYAN)

    safe_addstr(win, r2y+1, 2,
        f"{'EXCHANGE':<10} {'API KEY':<14} {'BALANCE':>12}  STATUS",
        cg(WHITE) | curses.A_BOLD)
    for i, acc in enumerate(state.accounts[:r2h-3]):
        ry  = r2y+2+i
        cc  = GREEN if acc["connected"] else RED
        bl  = f"{acc['balance']:.2f}" if acc["connected"] else "0.00"
        cs  = "● OK" if acc["connected"] else "✗ Offline"
        safe_addstr(win, ry, 2,  f"{acc['exchange']:<10}", cg(CYAN))
        safe_addstr(win, ry, 12, f"{acc['api_key']:<14}",  cg(WHITE))
        safe_addstr(win, ry, 28, f"{bl:>12}",              cg(GREEN))
        safe_addstr(win, ry, 42, f"  {cs}",                cg(cc))

    px2 = aw + 2
    mw2 = max_x - aw - 4
    chc = GREEN if state.market_change_24h >= 0 else RED
    chs = "+" if state.market_change_24h >= 0 else ""
    mkt_rows = [
        (f"Price:  {state.market_price:.2f} USDT",                       GREEN),
        (f"24h Chg:{chs}{state.market_change_24h:.2f}%",                 chc),
        (f"Hi/Lo:  {state.market_high_24h:.1f}/{state.market_low_24h:.1f}", GREEN),
        (f"Vol:    {_fmt_vol(state.market_volume)}",                      CYAN),
        (f"Pair:   {state.pair}  TF:{state.timeframe}",                  CYAN),
    ]
    for i, (txt, col) in enumerate(mkt_rows[:r2h-2]):
        safe_addstr(win, r2y+1+i, px2, txt[:mw2], cg(col))

    r3y = r2y + r2h
    n_active = len(getattr(state, 'active_symbols', set()))
    r3h      = min(max(5, n_active + 3), max(5, max_y - 4 - r3y))
    if r3y + r3h <= max_y - 4:
        _draw_watchlist(win, state, r3y, r3h, max_x)

    qy = max_y - 4
    if qy > r3y + r3h:
        try:
            win.attron(cg(GREEN))
            win.addstr(qy-1, 0, "─" * max_x)
            win.attroff(cg(GREEN))
        except curses.error:
            pass
        safe_addstr(win, qy-1, 2, " QUICK ACTIONS ", cg(GREEN) | curses.A_BOLD)

        bx = 2; gap = 1
        if not state.running:
            pending = state.mode == "real" and state.pending_confirm_action == "START"
            w = draw_btn(win, qy, bx, "⚠ Confirm Start" if pending else "▶ Start Bot",
                         "START", pending=pending, color=GREEN)
        else:
            w = draw_btn(win, qy, bx, "■ Stop Bot", "STOP", color=RED)
        bx += w + gap
        n_al = len(getattr(state, 'alerts', []))
        al_lbl = f"🔔 Alerts({n_al})" if n_al > 0 else "🔔 Alerts"
        for lbl, act, col in [
            ("↺ Restart",  "RESTART",      GREEN),
            ("⚙ Strategy", "STRATEGY",     GREEN),
            ("⚑ Mode/API", "MODE_SELECT",  GREEN),
            ("☰ Symbols",  "SYMBOLS",      GREEN),
            ("📋 Logs",    "LOGS",         GREEN),
            (al_lbl,        "ALERTS",       YELLOW if n_al > 0 else GREEN),
            ("☰ Menu",     "MENU",         GREEN),
            ("✖ Quit",     "EXIT",         RED),
        ]:
            w = draw_btn(win, qy, bx, lbl, act, color=col)
            bx += w + gap

        safe_addstr(win, qy+1, 2,
            "F1-F6 tabs  |  S=Start  R=Restart  L=Logs  B=Back  Q=Quit",
            cg(DIM))

    win.refresh()
