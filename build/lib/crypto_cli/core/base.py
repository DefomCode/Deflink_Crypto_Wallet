from abc import ABC, abstractmethod
from typing import Optional


class BlockchainAdapter(ABC):
    @abstractmethod
    def get_balance(self, address: str) -> Optional[float]: ...

    @abstractmethod
    def prepare_transaction(self, from_address: str, to_address: str, amount: float) -> Optional[dict]: ...

    @abstractmethod
    def estimate_tx_cost(self, tx: dict) -> float: ...

    @abstractmethod
    def sign_and_send(self, private_key: str, tx: dict) -> Optional[str]: ...

    @abstractmethod
    def wait_for_receipt(self, tx_hash: str, timeout: int = 300, poll_interval: int = 5) -> Optional[dict]: ...

    @abstractmethod
    def validate_private_key(self, private_key: str) -> bool: ...

    @property
    @abstractmethod
    def currency_symbol(self) -> str: ...

    @property
    @abstractmethod
    def explorer_url(self) -> str: ...
