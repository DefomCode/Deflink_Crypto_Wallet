from typing import Optional
from tronpy import Tron
from tronpy.keys import PrivateKey as TronPrivateKey
from crypto_cli.core.base import BlockchainAdapter


class TronAdapter(BlockchainAdapter):
    """Адаптер для Tron Mainnet."""

    def __init__(self):
        self.tron = Tron()

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
        except Exception:
            return None

    def prepare_transaction(self, from_address: str, to_address: str, amount: float) -> Optional[dict]:
        try:
            txn = (
                self.tron.trx.transfer(from_address, to_address, int(amount * 1_000_000))
                .memo("")
                .build()
            )
            return {"raw_txn": txn}
        except Exception:
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
        import time
        start = time.time()
        while time.time() - start < timeout:
            try:
                info = self.tron.get_transaction(tx_hash)
                if info and "ret" in info:
                    status = 1 if info["ret"][0].get("contractRet") == "SUCCESS" else 0
                    block = info.get("blockNumber")
                    fee_sun = info.get("fee", 0)
                    return {
                        "status": status,
                        "block_number": block,
                        "gas_used": fee_sun,
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
