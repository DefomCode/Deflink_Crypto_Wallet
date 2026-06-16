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


def get_pending_transactions():
    """Возвращает список pending-транзакций для проверки."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT tx_hash FROM transactions WHERE status = 'pending' ORDER BY created_at DESC"
        ).fetchall()
        return [row["tx_hash"] for row in rows]
    finally:
        conn.close()

def update_transaction_status(tx_hash: str, status: str, block_number: int | None = None, fee_eth: float | None = None, error_msg: str | None = None):
    """Обновляет статус транзакции в БД."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE transactions SET status=?, block_number=?, fee_eth=?, error_msg=?, updated_at=CURRENT_TIMESTAMP WHERE tx_hash=?",
            (status, block_number, fee_eth, error_msg, tx_hash)
        )
        conn.commit()
    finally:
        conn.close()

def get_all_transactions(filter_name: str | None = None, limit: int = 20, offset: int = 0):
    """Возвращает транзакции с поддержкой пагинации."""
    conn = get_connection()
    try:
        query = "SELECT * FROM transactions"
        params = []
        
        if filter_name:
            query += " WHERE from_name = ?"
            params.append(filter_name)
            
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_transaction_by_hash(tx_hash: str):
    """Возвращает полную информацию по хешу."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM transactions WHERE tx_hash = ?", (tx_hash,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def count_transactions(filter_name: str | None = None):
    """Считает общее количество транзакций для пагинации."""
    conn = get_connection()
    try:
        if filter_name:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM transactions WHERE from_name = ?", (filter_name,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as cnt FROM transactions").fetchone()
        return row["cnt"]
    finally:
        conn.close()
