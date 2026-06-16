import json
import os
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from web3 import Web3

VAULT_FILE = Path.home() / ".config" / "dcw" / "vault.json"

def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def create_wallet(name: str, password: str) -> str:
    """Генерирует ключ, шифрует и сохраняет. Возвращает адрес."""
    # 1. Генерация
    w3 = Web3()
    acct = w3.eth.account.create()
    
    # 2. Шифрование
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    f = Fernet(key)
    encrypted_pk = f.encrypt(acct.key.hex().encode())
    
    # 3. Сохранение
    VAULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if VAULT_FILE.exists():
        with open(VAULT_FILE, 'r') as file:
            data = json.load(file)
            
    data[name] = {
        "address": acct.address,
        "encrypted_pk": encrypted_pk.decode(),
        "salt": base64.b64encode(salt).decode()
    }
    
    with open(VAULT_FILE, 'w') as file:
        json.dump(data, file, indent=2)
        
    return acct.address

def import_wallet(name: str, private_key: str, password: str) -> str:
    """Импортирует существующий ключ, валидирует офлайн, шифрует и сохраняет."""
    w3 = Web3()
    
    # Офлайн-валидация: если ключ некорректен, здесь вылетит исключение
    try:
        acct = w3.eth.account.from_key(private_key)
    except Exception as e:
        raise ValueError(f"Невалидный приватный ключ: {e}")
    
    # Шифрование (та же логика, что и в create_wallet)
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    f = Fernet(key)
    encrypted_pk = f.encrypt(acct.key.hex().encode())
    
    VAULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if VAULT_FILE.exists():
        with open(VAULT_FILE, 'r') as file:
            data = json.load(file)
    
    if name in data:
        raise ValueError(f"Кошелек с именем '{name}' уже существует")
        
    data[name] = {
        "address": acct.address,
        "encrypted_pk": encrypted_pk.decode(),
        "salt": base64.b64encode(salt).decode()
    }
    
    with open(VAULT_FILE, 'w') as file:
        json.dump(data, file, indent=2)
        
    return acct.address

def list_wallets() -> dict:
    """Возвращает словарь {имя: адрес} всех кошельков из хранилища."""
    if not VAULT_FILE.exists():
        return {}
    with open(VAULT_FILE, 'r') as f:
        data = json.load(f)
    return {name: info["address"] for name, info in data.items()}
