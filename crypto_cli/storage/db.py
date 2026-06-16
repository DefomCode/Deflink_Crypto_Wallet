import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / ".config" / "dcw" / "dcw.db"

def get_connection():
    """Возвращает соединение с БД, создаёт таблицы если нет."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_hash TEXT UNIQUE NOT NULL,
            from_name TEXT NOT NULL,
            to_address TEXT NOT NULL,
            amount_eth REAL NOT NULL,
            fee_eth REAL,
            status TEXT NOT NULL DEFAULT 'pending',
            block_number INTEGER,
            error_msg TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wallet_cache (
            address TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            balance_eth REAL,
            balance_usd REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    return conn

def add_transaction(tx_hash: str, from_name: str, to_address: str, amount_eth: float, fee_eth: float):
    """Добавляет новую транзакцию со статусом pending."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO transactions (tx_hash, from_name, to_address, amount_eth, fee_eth, status) VALUES (?, ?, ?, ?, ?, 'pending')",
            (tx_hash, from_name, to_address, amount_eth, fee_eth)
        )
        conn.commit()
    finally:
        conn.close()

def update_wallet_cache(name: str, address: str, balance_eth: float, balance_usd: float | None):
    """Обновляет кэш баланса кошелька."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO wallet_cache (address, name, balance_eth, balance_usd, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP) ON CONFLICT(address) DO UPDATE SET balance_eth=?, balance_usd=?, updated_at=CURRENT_TIMESTAMP",
            (address, name, balance_eth, balance_usd, balance_eth, balance_usd)
        )
        conn.commit()
    finally:
        conn.close()
