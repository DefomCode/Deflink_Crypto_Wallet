from abc import ABC, abstractmethod
from typing import Optional


class BlockchainAdapter(ABC):
    """Базовый интерфейс для работы с блокчейном."""

    @abstractmethod
    def get_balance(self, address: str) -> Optional[float]:
        """Возвращает баланс в нативной валюте сети или None при ошибке."""
        ...

    @abstractmethod
    def prepare_transaction(self, from_address: str, to_address: str, amount: float) -> Optional[dict]:
        """Готовит транзакцию (nonce, gas, chainId). Возвращает dict или None."""
        ...

    @abstractmethod
    def estimate_tx_cost(self, tx: dict) -> float:
        """Возвращает стоимость комиссии в нативной валюте."""
        ...

    @abstractmethod
    def sign_and_send(self, private_key: str, tx: dict) -> Optional[str]:
        """Подписывает и отправляет транзакцию. Возвращает хеш или None."""
        ...

    @abstractmethod
    def wait_for_receipt(self, tx_hash: str, timeout: int = 300, poll_interval: int = 5) -> Optional[dict]:
        """Ждёт подтверждения. Возвращает receipt как dict или None."""
        ...

    @abstractmethod
    def validate_private_key(self, private_key: str) -> bool:
        """Проверяет валидность приватного ключа офлайн."""
        ...

    @property
    @abstractmethod
    def currency_symbol(self) -> str:
        """Символ валюты (ETH, TRX и т.д.)."""
        ...

    @property
    @abstractmethod
    def explorer_url(self) -> str:
        """Базовый URL эксплорера для формирования ссылок."""
        ...
