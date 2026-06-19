from typing import Optional
import time
from tronpy import Tron
from tronpy.providers import HTTPProvider
from tronpy.keys import PrivateKey as TronPrivateKey
from tronpy.exceptions import AddressNotFound
from crypto_cli.core.base import BlockchainAdapter


class TronAdapter(BlockchainAdapter):
    """Адаптер для Tron Mainnet с автовыбором рабочей ноды."""

    def __init__(self):
        endpoints = [
            "https://api.trongrid.io",
            "https://trx.mytokenpocket.vip",
            "https://api.tronstack.io",
        ]
        self.tron = None
        for ep in endpoints:
            try:
                provider = HTTPProvider(endpoint_uri=ep, timeout=8)
                t = Tron(provider=provider)
                t.get_latest_block_number()
                self.tron = t
                print(f"✅ Tron connected to {ep}")
                break
            except Exception as e:
                print(f"⚠️ Node {ep} unavailable: {type(e).__name__}")
                continue

        if self.tron is None:
            provider = HTTPProvider(endpoint_uri="https://api.trongrid.io", timeout=10)
            self.tron = Tron(provider=provider)
            print("⚠️ Using fallback TronGrid node")

    @property
    def currency_symbol(self) -> str:
        return "TRX"

    @property
    def explorer_url(self) -> str:
        return "https://tronscan.org"

    def get_balance(self, address: str) -> Optional[float]:
        try:
            balance_sun = self.tron.get_account_balance(address)
            return float(balance_sun) / 1_000_000
        except AddressNotFound:
            # Нормальная ситуация для новых/неактивированных аккаунтов
            return 0.0
        except Exception as e:
            print(f"Tron balance error for {address}: {e}")
            return None

    def prepare_transaction(self, from_address: str, to_address: str, amount: float) -> Optional[dict]:
        try:
            txn = (
                self.tron.trx.transfer(from_address, to_address, int(amount * 1_000_000))
                .memo("")
                .build()
            )
            return {"raw_txn": txn}
        except Exception as e:
            print(f"Prepare TRX tx error: {e}")
            return None

    def estimate_tx_cost(self, tx: dict) -> float:
        return 1.1

    def sign_and_send(self, private_key: str, tx: dict) -> Optional[str]:
        try:
            priv_key = TronPrivateKey(bytes.fromhex(private_key.replace("0x", "")))
            signed = tx["raw_txn"].sign(priv_key)
            result = signed.broadcast()
            return result.get("txid")
        except Exception as e:
            print(f"DEBUG TRX TX ERROR: {e}")
            return None

    def wait_for_receipt(self, tx_hash: str, timeout: int = 300, poll_interval: int = 5) -> Optional[dict]:
        start = time.time()
        while time.time() - start < timeout:
            try:
                info = self.tron.get_transaction(tx_hash)
                if info and "ret" in info and len(info["ret"]) > 0:
                    contract_ret = info["ret"][0].get("contractRet")
                    status = 1 if contract_ret == "SUCCESS" else 0
                    return {
                        "status": status,
                        "block_number": info.get("blockNumber"),
                        "gas_used": info.get("fee", 0),
                        "effective_gas_price": 1,
                    }
            except Exception:
                pass
            time.sleep(poll_interval)
        return None

    def validate_private_key(self, private_key: str) -> bool:
        try:
            TronPrivateKey(bytes.fromhex(private_key.replace("0x", "")))
            return True
        except Exception:
            return False
