import requests

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

def get_eth_usd_price() -> float | None:
    """Возвращает цену ETH в USD. При ошибке/отсутствии сети возвращает None."""
    try:
        resp = requests.get(
            COINGECKO_URL,
            params={"ids": "ethereum", "vs_currencies": "usd"},
            timeout=5,
            headers={"User-Agent": "DCW-Client/0.1"}
        )
        resp.raise_for_status()
        return float(resp.json()["ethereum"]["usd"])
    except Exception:
        return None

def get_trx_usd_price() -> float | None:
    """Возвращает курс TRX/USD или None."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=tron&vs_currencies=usd",
            timeout=5,
            headers={"User-Agent": "DefLink-Crypto-Wallet/1.0"},
        )
        return r.json()["tron"]["usd"]
    except Exception:
        return None
