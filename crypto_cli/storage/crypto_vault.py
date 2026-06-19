import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
import base64
import secrets

VAULT_PATH = Path.home() / ".config" / "dcw" / "vault.json"


# ==================== ШИФРОВАНИЕ (НОВЫЙ ФОРМАТ AES-GCM) ====================

def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt,
        iterations=600_000, backend=default_backend(),
    )
    return kdf.derive(password.encode())


def _encrypt(data: str, password: str) -> dict:
    salt = os.urandom(16)
    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, data.encode(), None)
    return {
        "salt": base64.b64encode(salt).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ct).decode(),
    }


def _decrypt_new(enc_data: dict, password: str) -> Optional[str]:
    try:
        salt = base64.b64decode(enc_data["salt"])
        nonce = base64.b64decode(enc_data["nonce"])
        ct = base64.b64decode(enc_data["ciphertext"])
        key = _derive_key(password, salt)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None).decode()
    except Exception:
        return None


# ==================== ДЕШИФРОВКА СТАРОГО ФОРМАТА (FERNET) ====================

def _decrypt_old(encrypted_pk: str, salt_b64: str, password: str) -> Optional[str]:
    """Расшифровывает старый формат Fernet."""
    try:
        # Старый формат использовал Fernet с ключом из пароля+соли
        # Восстанавливаем ключ как в старой версии
        salt = base64.urlsafe_b64decode(salt_b64)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt,
            iterations=600_000, backend=default_backend(),
        )
        key = kdf.derive(password.encode())
        fernet_key = base64.urlsafe_b64encode(key)
        f = Fernet(fernet_key)
        return f.decrypt(encrypted_pk.encode()).decode()
    except Exception:
        return None


# ==================== ЗАГРУЗКА / СОХРАНЕНИЕ ====================

def _load_vault() -> dict:
    if not VAULT_PATH.exists():
        VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        return {"wallets": {}}
    with open(VAULT_PATH, "r") as f:
        data = json.load(f)
    if "wallets" not in data:
        data["wallets"] = {}
    return data


def _save_vault(vault: dict):
    VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = VAULT_PATH.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(vault, f, indent=2)
    tmp_path.replace(VAULT_PATH)


# ==================== ПУБЛИЧНЫЕ ФУНКЦИИ ====================

def create_wallet(name: str, password: str, network_type: str = "ETH") -> str:
    vault = _load_vault()
    if name in vault["wallets"]:
        raise ValueError(f"Кошелек '{name}' уже существует")
    # Проверяем также старый формат
    raw = _load_raw_vault()
    if name in raw and name not in vault["wallets"]:
        raise ValueError(f"Кошелек '{name}' уже существует (старый формат)")

    network_type = network_type.upper()
    if network_type == "ETH":
        from web3 import Web3
        private_key = "0x" + secrets.token_hex(32)
        account = Web3().eth.account.from_key(private_key)
        address = account.address
        pk_clean = private_key.replace("0x", "")
    elif network_type == "TRX":
        from tronpy.keys import PrivateKey as TronPrivateKey
        pk_bytes = secrets.token_bytes(32)
        priv_key = TronPrivateKey(pk_bytes)
        address = priv_key.public_key.to_base58check_address()
        pk_clean = pk_bytes.hex()
    else:
        raise ValueError(f"Неподдерживаемая сеть: {network_type}")

    encrypted = _encrypt(pk_clean, password)
    vault["wallets"][name] = {
        "address": address,
        "encrypted_key": encrypted,
        "network": network_type,
    }
    _save_vault(vault)
    return address


def import_wallet(name: str, private_key: str, password: str, network_type: str = "ETH") -> str:
    vault = _load_vault()
    if name in vault["wallets"]:
        raise ValueError(f"Кошелек '{name}' уже существует")
    raw = _load_raw_vault()
    if name in raw and name not in vault["wallets"]:
        raise ValueError(f"Кошелек '{name}' уже существует (старый формат)")

    network_type = network_type.upper()
    if network_type == "ETH":
        from web3 import Web3
        account = Web3().eth.account.from_key(private_key)
        address = account.address
        pk_clean = private_key.replace("0x", "")
    elif network_type == "TRX":
        from tronpy.keys import PrivateKey as TronPrivateKey
        pk_bytes = bytes.fromhex(private_key.replace("0x", ""))
        priv_key = TronPrivateKey(pk_bytes)
        address = priv_key.public_key.to_base58check_address()
        pk_clean = pk_bytes.hex()
    else:
        raise ValueError(f"Неподдерживаемая сеть: {network_type}")

    encrypted = _encrypt(pk_clean, password)
    vault["wallets"][name] = {
        "address": address,
        "encrypted_key": encrypted,
        "network": network_type,
    }
    _save_vault(vault)
    return address


def _load_raw_vault() -> dict:
    """Загружает сырой JSON без преобразований."""
    if not VAULT_PATH.exists():
        return {}
    with open(VAULT_PATH, "r") as f:
        return json.load(f)


def list_wallets() -> Dict[str, Dict[str, Any]]:
    """Возвращает все кошельки из обоих форматов."""
    vault = _load_vault()
    raw = _load_raw_vault()
    result = {}

    # Новые кошельки
    for name, data in vault.get("wallets", {}).items():
        result[name] = {
            "address": data["address"],
            "network": data.get("network", "ETH"),
        }

    # Старые кошельки (в корне JSON, имеют encrypted_pk)
    for name, data in raw.items():
        if name == "wallets":
            continue
        if isinstance(data, dict) and "encrypted_pk" in data and name not in result:
            result[name] = {
                "address": data.get("address", ""),
                "network": "ETH",  # Старые всегда ETH
            }

    return result


def get_wallet_info(name: str) -> Optional[Dict[str, Any]]:
    vault = _load_vault()
    # Сначала ищем в новом формате
    data = vault.get("wallets", {}).get(name)
    if data:
        return {
            "address": data["address"],
            "network": data.get("network", "ETH"),
            "encrypted_key": data["encrypted_key"],
            "format": "new",
        }
    # Потом в старом
    raw = _load_raw_vault()
    old_data = raw.get(name)
    if old_data and isinstance(old_data, dict) and "encrypted_pk" in old_data:
        return {
            "address": old_data.get("address", ""),
            "network": "ETH",
            "encrypted_pk": old_data["encrypted_pk"],
            "salt": old_data["salt"],
            "format": "old",
        }
    return None


def decrypt_private_key(name: str, password: str) -> Optional[str]:
    info = get_wallet_info(name)
    if info is None:
        return None
    if info["format"] == "new":
        return _decrypt_new(info["encrypted_key"], password)
    else:
        return _decrypt_old(info["encrypted_pk"], info["salt"], password)


def rename_wallet(old_name: str, new_name: str):
    vault = _load_vault()
    raw = _load_raw_vault()

    # Проверяем оба формата
    if old_name in vault["wallets"]:
        if new_name in vault["wallets"] or (new_name in raw and new_name != "wallets"):
            raise ValueError(f"Имя '{new_name}' уже занято")
        vault["wallets"][new_name] = vault["wallets"].pop(old_name)
        _save_vault(vault)
    elif old_name in raw and old_name != "wallets":
        if new_name in vault["wallets"] or (new_name in raw and new_name != "wallets"):
            raise ValueError(f"Имя '{new_name}' уже занято")
        raw[new_name] = raw.pop(old_name)
        _save_vault(raw)
    else:
        raise ValueError(f"Кошелек '{old_name}' не найден")


def delete_wallet(name: str):
    vault = _load_vault()
    raw = _load_raw_vault()

    if name in vault["wallets"]:
        del vault["wallets"][name]
        _save_vault(vault)
    elif name in raw and name != "wallets":
        del raw[name]
        _save_vault(raw)
    else:
        raise ValueError(f"Кошелек '{name}' не найден")
