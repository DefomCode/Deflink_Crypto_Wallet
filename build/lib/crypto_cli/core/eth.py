from web3 import Web3
import requests
import time

# Более стабильные публичные RPC + User-Agent для обхода базовой защиты
ETH_RPC_URL = "https://ethereum-rpc.publicnode.com"

def get_eth_balance(address: str) -> float:
    """Возвращает баланс адреса в ETH. При ошибке сети возвращает None."""
    try:
        # Добавляем заголовки, чтобы RPC не думал, что мы бот
        session = requests.Session()
        session.headers.update({"User-Agent": "DCW-Client/0.1"})
        
        w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL, request_kwargs={"timeout": 10}, session=session))
        
        if not w3.is_connected():
            return None
        
        balance_wei = w3.eth.get_balance(Web3.to_checksum_address(address))
        return float(Web3.from_wei(balance_wei, 'ether'))
    except Exception:
        # По роадмапе: если интернета нет или RPC упал — не падаем
        return None

def prepare_transaction(from_address: str, to_address: str, amount_eth: float) -> dict | None:
    """Готовит транзакцию с актуальным газом и nonce. Возвращает dict или None при ошибке."""
    try:
        w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL, request_kwargs={"timeout": 10}))
        if not w3.is_connected():
            return None
            
        nonce = w3.eth.get_transaction_count(Web3.to_checksum_address(from_address))
        gas_price = w3.eth.gas_price
        
        tx = {
            'nonce': nonce,
            'to': Web3.to_checksum_address(to_address),
            'value': w3.to_wei(amount_eth, 'ether'),
            'gas': 21000,  # Стандарт для простого перевода ETH
            'gasPrice': gas_price,
            'chainId': w3.eth.chain_id
        }
        return tx
    except Exception:
        return None

def estimate_tx_cost(tx: dict) -> float:
    """Возвращает стоимость комиссии в ETH."""
    return float(Web3.from_wei(tx['gas'] * tx['gasPrice'], 'ether'))

def sign_and_send_transaction(private_key: str, tx: dict) -> str | None:
    """Подписывает транзакцию и отправляет в сеть. Возвращает хеш или None при ошибке."""
    try:
        w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL, request_kwargs={"timeout": 10}))
        if not w3.is_connected():
            return None
            
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        return tx_hash.hex()
    except Exception as e:
        # Логируем ошибку для отладки, но пользователю возвращаем None
        print(f"DEBUG TX ERROR: {e}") 
        return None

def wait_for_receipt(tx_hash: str, timeout: int = 300, poll_interval: int = 5) -> dict | None:
    """
    Ждет подтверждения транзакции.
    Возвращает receipt при успехе/ошибке или None при таймауте/прерывании.
    """
    try:
        w3 = Web3(Web3.HTTPProvider(ETH_RPC_URL, request_kwargs={"timeout": 10}))
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                receipt = w3.eth.get_transaction_receipt(tx_hash)
                if receipt is not None:
                    return receipt
            except Exception:
                pass  # Транзакция еще не в блоке, ждем дальше
                
            time.sleep(poll_interval)
            
        return None  # Таймаут
    except KeyboardInterrupt:
        return None  # Пользователь нажал Ctrl+C
