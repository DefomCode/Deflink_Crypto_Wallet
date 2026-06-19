from typing import Optional
from web3 import Web3
from crypto_cli.core.base import BlockchainAdapter

ETH_RPC_URL = "https://ethereum-rpc.publicnode.com"


class EthAdapter(BlockchainAdapter):
    """Адаптер для Ethereum Mainnet."""

    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL, request_kwargs={"timeout": 10}))

    @property
    def currency_symbol(self) -> str:
        return "ETH"

    @property
    def explorer_url(self) -> str:
        return "https://etherscan.io"

    def get_balance(self, address: str) -> Optional[float]:
        try:
            if not self.w3.is_connected():
                return None
            balance_wei = self.w3.eth.get_balance(Web3.to_checksum_address(address))
            return float(Web3.from_wei(balance_wei, 'ether'))
        except Exception:
            return None

    def prepare_transaction(self, from_address: str, to_address: str, amount: float) -> Optional[dict]:
        try:
            if not self.w3.is_connected():
                return None
            nonce = self.w3.eth.get_transaction_count(Web3.to_checksum_address(from_address))
            gas_price = self.w3.eth.gas_price
            return {
                'nonce': nonce,
                'to': Web3.to_checksum_address(to_address),
                'value': self.w3.to_wei(amount, 'ether'),
                'gas': 21000,
                'gasPrice': gas_price,
                'chainId': self.w3.eth.chain_id,
            }
        except Exception:
            return None

    def estimate_tx_cost(self, tx: dict) -> float:
        return float(Web3.from_wei(tx['gas'] * tx['gasPrice'], 'ether'))

    def sign_and_send(self, private_key: str, tx: dict) -> Optional[str]:
        try:
            signed = self.w3.eth.account.sign_transaction(tx, private_key=private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            return tx_hash.hex()
        except Exception as e:
            print(f"DEBUG TX ERROR: {e}")
            return None

    def wait_for_receipt(self, tx_hash: str, timeout: int = 300, poll_interval: int = 5) -> Optional[dict]:
        import time
        start = time.time()
        while time.time() - start < timeout:
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt is not None:
                    return {
                        'status': receipt.status,
                        'block_number': receipt.blockNumber,
                        'gas_used': receipt.gasUsed,
                        'effective_gas_price': receipt.effectiveGasPrice,
                    }
            except Exception:
                pass
            time.sleep(poll_interval)
        return None

    def validate_private_key(self, private_key: str) -> bool:
        try:
            self.w3.eth.account.from_key(private_key)
            return True
        except Exception:
            return False
