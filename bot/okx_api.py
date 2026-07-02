"""OKX REST API helpers — implements same interface as bybit_api.py."""
import urllib.request
import urllib.parse
import json
import hmac
import hashlib
import time

BASE = "https://www.okx.com"
# Demo/testnet uses same base; OKX distinguishes via API key permissions

def _get(path: str, params: dict = None) -> dict:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())

def _sign(api_key: str, api_secret: str, ts: str, payload: str) -> str:
    message = ts + "GET" + payload
    mac = hmac.new(api_secret.encode(), message.encode(), hashlib.sha256)
    return mac.hexdigest()

def _get_auth(api_key: str, api_secret: str, path: str, params: dict = None) -> dict:
    ts = str(int(time.time() * 1000))
    qs = urllib.parse.urlencode(params or {})
    sig = _sign(api_key, api_secret, ts, path + ("?" + qs if qs else ""))
    url = BASE + path + ("?" + qs if qs else "")
    headers = {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": sig,
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": "",  # user must set this if needed, most keys don't need it
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())

def _post_auth(api_key: str, api_secret: str, path: str, body: dict) -> dict:
    ts = str(int(time.time() * 1000))
    payload = json.dumps(body, separators=(",", ":"))
    sig = _sign(api_key, api_secret, ts, path)
    url = BASE + path
    headers = {
        "OK-ACCESS-KEY": api_key,
        "OK-ACCESS-SIGN": sig,
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": "",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=payload.encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())

# ── Public ────────────────────────────────────────────────────────────────────

def get_ticker(symbol: str = "BTC-USDT", market: str = "futures") -> dict:
    """Return {'price': float, 'change24h': float, 'high24h': float, 'low24h': float, 'volume': float}"""
    inst_type = "SWAP" if market == "futures" else "SPOT"
    data = _get("/api/v5/market/ticker", {"instId": symbol, "instType": inst_type})
    ticker_list = data.get("data", [])
    if not ticker_list:
        return {"price": 0.0, "change24h": 0.0, "high24h": 0.0, "low24h": 0.0, "volume": 0.0}
    t = ticker_list[0]
    return {
        "price": float(t.get("last", 0)),
        "change24h": float(t.get("open24h", 0)) and (float(t.get("last", 0)) - float(t.get("open24h", 0))) / float(t.get("open24h", 1)) * 100 or 0.0,
        "high24h": float(t.get("high24h", 0)),
        "low24h": float(t.get("low24h", 0)),
        "volume": float(t.get("vol24h", 0)),
    }

def get_klines(symbol: str = "BTC-USDT", interval: str = "15m", limit: int = 50, market: str = "futures") -> list:
    """Return list of {time, open, high, low, close, volume}."""
    inst_type = "SWAP" if market == "futures" else "SPOT"
    data = _get("/api/v5/market/candles", {
        "instId": symbol,
        "bar": interval,
        "limit": str(limit),
    })
    result = []
    for k in data.get("data", []):
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

def test_connection(api_key: str, api_secret: str, market: str = "futures") -> tuple[bool, str]:
    """Returns (ok: bool, message: str)"""
    try:
        data = _get_auth(api_key, api_secret, "/api/v5/account/balance")
        if data.get("code") == "0":
            details = data.get("data", [])
            bal = 0.0
            if details:
                for d in details[0].get("details", []):
                    if d.get("ccy") == "USDT":
                        bal = float(d.get("availBal", 0))
                        break
            return True, f"OK - Balance: {bal:.2f} USDT ({market})"
        return False, data.get("msg", "Unknown error")
    except Exception as e:
        return False, str(e)

def get_wallet_balance(api_key: str, api_secret: str, market: str = "futures") -> float:
    try:
        data = _get_auth(api_key, api_secret, "/api/v5/account/balance")
        if data.get("code") == "0":
            details = data.get("data", [])
            if details:
                for d in details[0].get("details", []):
                    if d.get("ccy") == "USDT":
                        return float(d.get("availBal", 0))
    except Exception:
        pass
    return 0.0

def get_positions(api_key: str, api_secret: str, symbol: str = "BTC-USDT", market: str = "futures") -> list:
    try:
        inst_type = "SWAP" if market == "futures" else "SPOT"
        params = {"instType": inst_type}
        if inst_type == "SWAP":
            params["instId"] = symbol
        data = _get_auth(api_key, api_secret, "/api/v5/account/positions", params)
        if data.get("code") == "0":
            result = []
            for p in data.get("data", []):
                size = float(p.get("pos", 0))
                if size > 0:
                    entry = float(p.get("avgPx", 0))
                    current = float(p.get("markPx", entry))
                    side = "LONG" if p.get("posSide", "long") == "long" else "SHORT"
                    unreal = float(p.get("unrealizedPnl", 0))
                    pct = (unreal / (entry * size)) * 100 if entry * size > 0 else 0
                    result.append({
                        "symbol": symbol,
                        "side": side,
                        "size": size,
                        "entry": entry,
                        "current": current,
                        "pnl_usdt": round(unreal, 2),
                        "pnl_pct": round(pct, 3),
                    })
            return result
    except Exception:
        pass
    return []

def set_leverage(api_key: str, api_secret: str, symbol: str, leverage: int, market: str = "futures") -> bool:
    if market != "futures":
        return True
    try:
        body = {
            "instId": symbol,
            "lever": str(leverage),
            "mgnMode": "cross",
        }
        data = _post_auth(api_key, api_secret, "/api/v5/account/set-leverage", body)
        return data.get("code") == "0"
    except Exception:
        return False

def place_order(api_key: str, api_secret: str,
                symbol: str, side: str, qty: float,
                order_type: str = "market",
                take_profit: float = None,
                stop_loss: float = None,
                reduce_only: bool = False,
                market: str = "futures") -> dict:
    """Place an order. Returns the order result dict with ordId."""
    side_map = {"buy": "buy", "sell": "sell"}
    okx_side = side_map.get(side.lower(), side.lower())
    body = {
        "instId": symbol,
        "tdMode": "cross" if market == "futures" else "cash",
        "side": okx_side,
        "ordType": order_type,
        "sz": str(qty),
    }
    if reduce_only:
        body["reduceOnly"] = "true"
    if market == "futures":
        body["lever"] = "3"
    if take_profit is not None:
        body["tpTriggerPx"] = str(take_profit)
        body["tpOrdPx"] = "-1"
    if stop_loss is not None:
        body["slTriggerPx"] = str(stop_loss)
        body["slOrdPx"] = "-1"
    try:
        data = _post_auth(api_key, api_secret, "/api/v5/trade/order", body)
        if data.get("code") == "0":
            return data.get("data", [{}])[0]
        return {"error": data.get("msg", "Unknown error")}
    except Exception as e:
        return {"error": str(e)}

def cancel_order(api_key: str, api_secret: str, symbol: str, order_id: str, market: str = "futures") -> bool:
    try:
        body = {
            "instId": symbol,
            "ordId": order_id,
        }
        data = _post_auth(api_key, api_secret, "/api/v5/trade/cancel-order", body)
        return data.get("code") == "0"
    except Exception:
        return False
