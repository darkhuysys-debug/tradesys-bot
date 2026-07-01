"""Bybit REST API helpers — uses only stdlib (no extra packages)."""
import urllib.request
import urllib.parse
import json
import hmac
import hashlib
import time

BASE_DEMO = "https://api-demo.bybit.com"
BASE_MAIN = "https://api.bybit.com"

def _get(path: str, params: dict = None, demo: bool = True) -> dict:
    base = BASE_DEMO if demo else BASE_MAIN
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())

def _sign(api_key: str, api_secret: str, ts: str, recv_window: str, payload: str) -> str:
    raw = ts + api_key + recv_window + payload
    return hmac.new(api_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()

def _get_auth(api_key: str, api_secret: str, path: str, params: dict = None, demo: bool = True) -> dict:
    base = BASE_DEMO if demo else BASE_MAIN
    ts   = str(int(time.time() * 1000))
    recv = "5000"
    qs   = urllib.parse.urlencode(params or {})
    sig  = _sign(api_key, api_secret, ts, recv, qs)
    url  = base + path + ("?" + qs if qs else "")
    headers = {
        "X-BAPI-API-KEY":     api_key,
        "X-BAPI-TIMESTAMP":   ts,
        "X-BAPI-RECV-WINDOW": recv,
        "X-BAPI-SIGN":        sig,
        "Content-Type":       "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())

def _post_auth(api_key: str, api_secret: str, path: str, body: dict, demo: bool = True) -> dict:
    base = BASE_DEMO if demo else BASE_MAIN
    ts   = str(int(time.time() * 1000))
    recv = "5000"
    payload = json.dumps(body, separators=(",", ":"))
    sig  = _sign(api_key, api_secret, ts, recv, payload)
    url  = base + path
    headers = {
        "X-BAPI-API-KEY":     api_key,
        "X-BAPI-TIMESTAMP":   ts,
        "X-BAPI-RECV-WINDOW": recv,
        "X-BAPI-SIGN":        sig,
        "Content-Type":       "application/json",
    }
    req = urllib.request.Request(url, data=payload.encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())

# ── Public ────────────────────────────────────────────────────────────────────

def get_ticker(symbol: str = "BTCUSDT", demo: bool = True) -> dict:
    """Return {'price': float, 'change24h': float, 'high24h': float, 'low24h': float, 'volume': float}"""
    data = _get("/v5/market/tickers", {"category": "linear", "symbol": symbol}, demo=demo)
    t = data["result"]["list"][0]
    return {
        "price":     float(t["lastPrice"]),
        "change24h": float(t.get("price24hPcnt", 0)) * 100,
        "high24h":   float(t["highPrice24h"]),
        "low24h":    float(t["lowPrice24h"]),
        "volume":    float(t.get("volume24h", 0)) / 1000,
    }

def get_klines(symbol: str = "BTCUSDT", interval: str = "15", limit: int = 50, demo: bool = True) -> list:
    """Return list of {time, open, high, low, close, volume}."""
    data = _get("/v5/market/kline", {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit,
    }, demo=demo)
    result = []
    for k in data.get("result", {}).get("list", []):
        result.append({
            "time":   int(k[0]),
            "open":   float(k[1]),
            "high":   float(k[2]),
            "low":    float(k[3]),
            "close":  float(k[4]),
            "volume": float(k[5]),
        })
    return result

# ── Private ──────────────────────────────────────────────────────────────────

def test_connection(api_key: str, api_secret: str, demo: bool = True) -> tuple[bool, str]:
    """Returns (ok: bool, message: str)"""
    try:
        data = _get_auth(api_key, api_secret, "/v5/account/wallet-balance",
                         {"accountType": "UNIFIED"}, demo=demo)
        if data.get("retCode") == 0:
            coins = data["result"]["list"][0]["coin"]
            usdt  = next((c for c in coins if c["coin"] == "USDT"), None)
            bal   = float(usdt["walletBalance"]) if usdt else 0.0
            return True, f"OK - Balance: {bal:.2f} USDT"
        return False, data.get("retMsg", "Unknown error")
    except Exception as e:
        return False, str(e)

def get_wallet_balance(api_key: str, api_secret: str, demo: bool = True) -> float:
    try:
        data = _get_auth(api_key, api_secret, "/v5/account/wallet-balance",
                         {"accountType": "UNIFIED"}, demo=demo)
        if data.get("retCode") == 0:
            coins = data["result"]["list"][0]["coin"]
            usdt  = next((c for c in coins if c["coin"] == "USDT"), None)
            return float(usdt["walletBalance"]) if usdt else 0.0
    except Exception:
        pass
    return 0.0

def get_positions(api_key: str, api_secret: str, symbol: str = "BTCUSDT", demo: bool = True) -> list:
    try:
        data = _get_auth(api_key, api_secret, "/v5/position/list",
                         {"category": "linear", "symbol": symbol}, demo=demo)
        if data.get("retCode") == 0:
            result = []
            for p in data["result"]["list"]:
                if float(p["size"]) > 0:
                    entry   = float(p["avgPrice"])
                    current = float(p.get("markPrice", entry))
                    size    = float(p["size"])
                    raw_side = p["side"].upper()
                    side    = "LONG" if raw_side == "BUY" else "SHORT"
                    unreal  = float(p.get("unrealisedPnl", 0))
                    pct     = (unreal / (entry * size)) * 100 if entry * size > 0 else 0
                    lev_raw = p.get("leverage")
                    leverage = float(lev_raw) if lev_raw not in (None, "") else 0.0
                    tp_raw  = p.get("takeProfit")
                    sl_raw  = p.get("stopLoss")
                    tp      = float(tp_raw) if tp_raw not in (None, "") else 0.0
                    sl      = float(sl_raw) if sl_raw not in (None, "") else 0.0
                    result.append({
                        "symbol":    p["symbol"].replace("USDT", "/USDT"),
                        "side":      side,
                        "size":      size,
                        "entry":     entry,
                        "current":   current,
                        "pnl_usdt":  round(unreal, 2),
                        "pnl_pct":   round(pct, 3),
                        "position_idx": int(p.get("positionIdx", 0)),
                        "leverage":  leverage,
                        "tp":        tp,
                        "sl":        sl,
                    })
            return result
    except Exception:
        pass
    return []

def set_leverage(api_key: str, api_secret: str, symbol: str, leverage: int, demo: bool = True) -> bool:
    try:
        data = _post_auth(api_key, api_secret, "/v5/position/set-leverage", {
            "category": "linear",
            "symbol": symbol,
            "buyLeverage": str(leverage),
            "sellLeverage": str(leverage),
        }, demo=demo)
        return data.get("retCode") == 0
    except Exception:
        return False

def place_order(api_key: str, api_secret: str,
                symbol: str, side: str, qty: float,
                order_type: str = "Market",
                take_profit: float = None,
                stop_loss: float = None,
                reduce_only: bool = False,
                position_idx: int = None,
                demo: bool = True) -> dict:
    """Place an order. Returns the order result dict with orderId."""
    side_str = "Buy" if side.upper() == "BUY" else "Sell"
    body = {
        "category": "linear",
        "symbol": symbol,
        "side": side_str,
        "orderType": order_type,
        "qty": str(qty),
        "timeInForce": "IOC" if order_type == "Market" else "GTC",
    }
    if reduce_only:
        body["reduceOnly"] = True
    if position_idx is not None:
        body["positionIdx"] = str(position_idx)
    if take_profit is not None:
        body["takeProfit"] = str(take_profit)
    if stop_loss is not None:
        body["stopLoss"] = str(stop_loss)
    try:
        data = _post_auth(api_key, api_secret, "/v5/order/create", body, demo=demo)
        if data.get("retCode") == 0:
            return data.get("result", {})
        return {"error": data.get("retMsg", "Unknown error")}
    except Exception as e:
        return {"error": str(e)}

def cancel_order(api_key: str, api_secret: str, symbol: str, order_id: str, demo: bool = True) -> bool:
    try:
        data = _post_auth(api_key, api_secret, "/v5/order/cancel", {
            "category": "linear",
            "symbol": symbol,
            "orderId": order_id,
        }, demo=demo)
        return data.get("retCode") == 0
    except Exception:
        return False

def switch_position_mode(api_key: str, api_secret: str, symbol: str, mode: str, demo: bool = True) -> dict:
    """Switch position mode. mode: 'one-way' (0) or 'hedge' (1)."""
    trade_mode = 0 if mode == "one-way" else 1
    try:
        data = _post_auth(api_key, api_secret, "/v5/position/switch-mode", {
            "category": "linear",
            "symbol": symbol,
            "tradeMode": trade_mode,
        }, demo=demo)
        return data
    except Exception as e:
        return {"retCode": -1, "retMsg": str(e)}
