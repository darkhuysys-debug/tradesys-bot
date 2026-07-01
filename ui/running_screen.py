import curses
import time
from .base import draw_box, safe_addstr, draw_btn, reg, clear_clicks, get_version, heartbeat_on, step_toward, draw_header, draw_signal_badge_box
from .colors import cg, GREEN, RED, YELLOW, CYAN, WHITE, DIM


def draw_running(win, state):
    clear_clicks()
    win.erase()
    max_y, max_x = win.getmaxyx()

    draw_header(win, max_x, "RUNNING", state)
    y0 = 3

    sc = GREEN if state.status == "RUNNING" else RED
    status_attr = cg(sc) | curses.A_BOLD
    if state.status == "RUNNING" and not heartbeat_on():
        status_attr = cg(sc)

    safe_addstr(win, y0, 2,  "STATUS:",    cg(WHITE))
    safe_addstr(win, y0, 10, state.status, status_attr)
    safe_addstr(win, y0, 22, f"PAIR: {state.pair}",       cg(CYAN))
    safe_addstr(win, y0, 36, f"TF: {state.timeframe}",    cg(CYAN))
    safe_addstr(win, y0, 46, f"LEV: {state.leverage}x",   cg(YELLOW))
    safe_addstr(win, y0, 56, f"UPTIME: {state.get_uptime_str()}", cg(GREEN))

    bx = max_x - 38
    start_pending = (state.mode == "real" and
                      state.pending_confirm_action == "START")
    if start_pending:
        w = draw_btn(win, y0, bx, "⚠ Confirm Start", "START", pending=True)
    else:
        w = draw_btn(win, y0, bx, "▶ Start",   "START",   color=GREEN)
    bx += 12
    draw_btn(win, y0, bx, "■ Stop",    "STOP",    color=RED);   bx += 11
    draw_btn(win, y0, bx, "↺ Restart", "RESTART", color=YELLOW)

    half = max_x // 2

    mh = 7
    draw_box(win, y0+1, 0,    mh, half, "MARKET DATA", GREEN)
    draw_box(win, y0+1, half, mh, half, "ACCOUNT",     GREEN)

    chc = GREEN if state.market_change_24h >= 0 else RED
    chs = "+" if state.market_change_24h >= 0 else ""
    for i, (k, v, c) in enumerate([
        ("Price:",    f"{state.market_price:.1f} USDT",          GREEN),
        ("24h Chg:",  f"{chs}{state.market_change_24h:.2f}%",    chc),
        ("High/Low:", f"{state.market_high_24h:.1f} / {state.market_low_24h:.1f}", GREEN),
        ("Volume:",   f"{state.market_volume:.2f}K",             GREEN),
        ("Strategy:", state.strategy,                            CYAN),
    ]):
        safe_addstr(win, y0+2+i, 2,  k, cg(WHITE))
        safe_addstr(win, y0+2+i, 15, v, cg(c))

    main_acc = state.get_main_account()
    bal = main_acc["balance"] if main_acc else 0.0

    state.equity_display = step_toward(state.equity_display, state.equity,
                                        max_step=max(0.5, abs(state.equity - state.equity_display) * 0.3))
    state.pnl_display = step_toward(state.pnl_display, state.pnl_today,
                                     max_step=max(0.3, abs(state.pnl_today - state.pnl_display) * 0.3))

    pc  = GREEN if state.pnl_usdt >= 0 else RED
    sg  = "+" if state.pnl_usdt >= 0 else ""
    pnl_disp_sg = "+" if state.pnl_display >= 0 else ""
    for i, (k, v, c) in enumerate([
        ("Balance:",   f"{bal:.2f} USDT",                GREEN),
        ("Equity:",    f"{state.equity_display:.2f} USDT", GREEN),
        ("PNL Today:", f"{pnl_disp_sg}{state.pnl_display:.2f} USDT", pc),
        ("PNL %:",     f"{sg}{state.pnl_pct:.2f}%",       pc),
        ("Positions:", f"{len(state.positions)} / {state.max_positions}", WHITE),
    ]):
        safe_addstr(win, y0+2+i, half+2,  k, cg(WHITE))
        safe_addstr(win, y0+2+i, half+15, v, cg(c))

    if len(state.pnl_history) > 1:
        spark_chars = "▁▂▃▄▅▆▇█"
        vals = state.pnl_history[-20:]
        mn = min(vals)
        mx = max(vals)
        rng = mx - mn if mx != mn else 1
        line = ""
        for v in vals:
            idx = min(7, int((v - mn) / rng * 7))
            line += spark_chars[idx]
        safe_addstr(win, y0+7, half+2, "PNL Spark:", cg(WHITE))
        safe_addstr(win, y0+7, half+14, line, cg(pc))

    sy = y0+1+mh
    sh = 5
    draw_box(win, sy, 0,    sh, half, "SIGNAL",     CYAN)
    draw_box(win, sy, half, sh, half, "INDICATORS", CYAN)

    sig_col = GREEN if state.signal == "BUY" else RED if state.signal == "SELL" else YELLOW
    sig_arrow = "▲" if state.signal == "BUY" else "▼" if state.signal == "SELL" else "■"
    safe_addstr(win, sy+1, 2, "Signal:", cg(DIM))
    sig_badge = f" {sig_arrow} {state.signal} "
    bw = len(sig_badge) + 2
    safe_addstr(win, sy+1, 10, "┌" + "─" * bw + "┐", cg(sig_col))
    safe_addstr(win, sy+2, 10, "│" + sig_badge + "│", cg(sig_col) | curses.A_BOLD)
    safe_addstr(win, sy+3, 10, "└" + "─" * bw + "┘", cg(sig_col))
    safe_addstr(win, sy+2, 10+bw+2, f"SCORE: {state.score}", cg(sig_col) | curses.A_BOLD)

    if state.signal_reasons:
        rx = 2; ry = sy+2
        for reason in state.signal_reasons[:4]:
            tag = f" [{reason[:20]}] "
            if rx + len(tag) > half - 2:
                rx = 2; ry += 1
            if ry >= sy + sh:
                break
            safe_addstr(win, ry, rx, tag, cg(sig_col))
            rx += len(tag) + 1
    safe_addstr(win, sy+sh-2, 2, f"TP / SL: {state.take_profit}% / {state.stop_loss}%", cg(WHITE))
    safe_addstr(win, sy+sh-1, 2, f"Risk/Trade: {state.risk_per_trade}%", cg(WHITE))

    macd_c = GREEN if state.macd_histogram >= 0 else RED
    rsi_col = RED if state.current_rsi > 70 else GREEN if state.current_rsi < 30 else CYAN
    rsi_lbl = f"{state.current_rsi:.1f} ← {'overbought' if state.current_rsi > 70 else 'oversold' if state.current_rsi < 30 else 'neutral'}"
    macd_arrow = "↑" if state.macd_histogram >= 0 else "↓"
    cooldown_ok = getattr(state, 'cooldown_remaining', 0) == 0
    cons_loss   = getattr(state, 'consecutive_losses', 0)
    max_cons    = getattr(state, 'max_consecutive_losses', 3)
    ind_rows = [
        (f"RSI(14):",    rsi_lbl,                                                  rsi_col),
        (f"MACD hist:",  f"{state.macd_histogram:+.2f} {macd_arrow}",             macd_c),
        (f"EMA 9/21:",   f"{state.current_ema_fast:.0f} / {state.current_ema_slow:.0f}", CYAN),
        (f"BB:",         f"{state.bb_lower:.0f} — {state.bb_upper:.0f}",     CYAN),
        (f"BB Mid:",     f"{(state.bb_lower+state.bb_upper)/2:.0f}",              WHITE),
        (f"Vol SMA:",    f"{getattr(state,'market_volume',0):.1f}K",              CYAN),
        (f"Cooldown:",   "OK (no cooldown)" if cooldown_ok else f"{getattr(state,'cooldown_remaining',0)} candles", GREEN if cooldown_ok else YELLOW),
        (f"Cons.Loss:",  f"{cons_loss} / {max_cons}",                             GREEN if cons_loss == 0 else RED),
    ]
    for ii, (ik, iv, ic) in enumerate(ind_rows):
        if sy + 1 + ii >= sy + sh:
            break
        safe_addstr(win, sy+1+ii, half+2, f"{ik:<12}", cg(DIM))
        safe_addstr(win, sy+1+ii, half+14, iv, cg(ic))

    py = sy + sh
    ph = min(len(state.positions) + 3, 6)
    draw_box(win, py, 0, ph, max_x, "OPEN POSITIONS", GREEN)
    safe_addstr(win, py+1, 2,
        f"{'SYMBOL':<12} {'SIDE':<6} {'SIZE':>6} {'ENTRY':>9} {'CURRENT':>9} {'PNL USDT':>10} {'PNL%':>7} {'STATUS':<10}",
        cg(WHITE) | curses.A_BOLD)
    for i, pos in enumerate(state.positions[:max(ph-3,1)]):
        y   = py+2+i
        pc2 = GREEN if pos["pnl_usdt"] >= 0 else RED
        sg2 = "+" if pos["pnl_usdt"] >= 0 else ""
        safe_addstr(win, y, 2,
            f"{pos['symbol']:<12} {pos['side']:<6} {pos['size']:>6.3f}"
            f" {pos['entry']:>9.1f} {pos['current']:>9.1f}", cg(WHITE))
        safe_addstr(win, y, 49, f"{sg2}{pos['pnl_usdt']:>9.2f}", cg(pc2))
        safe_addstr(win, y, 60, f" {sg2}{abs(pos['pnl_pct']):.3f}%", cg(pc2))

    tr_y = py + ph
    tr_h = max_y - tr_y - 3
    if tr_h >= 4:
        draw_box(win, tr_y, 0, tr_h, max_x, "RECENT TRADES", GREEN)
        safe_addstr(win, tr_y+1, 2,
            f"{'TIME':<10} {'SYMBOL':<12} {'SIDE':<6} {'SIZE':>6} {'PRICE':>9} {'PNL USDT':>10} {'RESULT':<10} {'ORDER ID':<12}",
            cg(WHITE) | curses.A_BOLD)
        for i, tr in enumerate(state.recent_trades[:tr_h-3]):
            y   = tr_y+2+i
            tc2 = GREEN if tr["pnl_usdt"] >= 0 else RED
            sg3 = "+" if tr["pnl_usdt"] >= 0 else ""
            sc2 = GREEN if tr["side"] == "BUY" else RED
            safe_addstr(win, y, 2,  f"{tr['time']:<10} {tr['symbol']:<12}", cg(WHITE))
            safe_addstr(win, y, 26, f"{tr['side']:<6}", cg(sc2))
            safe_addstr(win, y, 33, f"{tr['size']:>6.3f} {tr['price']:>9.1f}", cg(WHITE))
            safe_addstr(win, y, 50, f"{sg3}{tr['pnl_usdt']:>10.2f}", cg(tc2))
            res_col = GREEN if "TP" in tr.get("result","") else RED if "SL" in tr.get("result","") else WHITE
            safe_addstr(win, y, 63, f"{tr.get('result','─'):<10}", cg(res_col))
            safe_addstr(win, y, 74, f"{tr.get('order_id','─'):<12}", cg(DIM))

    bx = 2
    w = draw_btn(win, max_y-1, bx, "☰ Menu",     "MENU");     bx += w+1
    w = draw_btn(win, max_y-1, bx, "⚙ Strategy", "STRATEGY"); bx += w+1
    w = draw_btn(win, max_y-1, bx, "📋 Logs",    "LOGS");     bx += w+1
    draw_btn(win, max_y-1, bx, "✖ Quit", "EXIT", color=RED)

    foot = f"Signal: {state.signal} ({state.score})  |  Risk: {state.risk_per_trade}% / trade"
    safe_addstr(win, max_y-1, max_x - len(foot) - 2, foot, cg(GREEN))

    
    from .base import draw_theme_bar
    draw_theme_bar(win, max_y, max_x)
    win.refresh()
