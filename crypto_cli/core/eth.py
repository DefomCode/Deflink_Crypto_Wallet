from web3 import Web3
import requests

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
