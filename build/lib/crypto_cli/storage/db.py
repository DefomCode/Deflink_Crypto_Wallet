import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".config" / "dcw" / "dcw.db"


def get_connection():
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
            network_type TEXT NOT NULL DEFAULT 'ETH',
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
            network_type TEXT NOT NULL DEFAULT 'ETH',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Миграция для старых БД без network_type
    try:
        conn.execute("ALTER TABLE transactions ADD COLUMN network_type TEXT NOT NULL DEFAULT 'ETH'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE wallet_cache ADD COLUMN network_type TEXT NOT NULL DEFAULT 'ETH'")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    return conn


def add_transaction(tx_hash, from_name, to_address, amount, fee, network_type="ETH"):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO transactions (tx_hash, from_name, to_address, amount_eth, fee_eth, status, network_type) VALUES (?, ?, ?, ?, ?, 'pending', ?)",
            (tx_hash, from_name, to_address, amount, fee, network_type),
        )
        conn.commit()
    finally:
        conn.close()


def update_transaction_status(tx_hash, status, block_number=None, fee_eth=None, error_msg=None):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE transactions SET status=?, block_number=?, fee_eth=?, error_msg=?, updated_at=CURRENT_TIMESTAMP WHERE tx_hash=?",
            (status, block_number, fee_eth, error_msg, tx_hash),
        )
        conn.commit()
    finally:
        conn.close()


def get_pending_transactions():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT tx_hash FROM transactions WHERE status = 'pending' ORDER BY created_at DESC").fetchall()
        return [row["tx_hash"] for row in rows]
    finally:
        conn.close()


def get_all_transactions(filter_name=None, limit=20, offset=0):
    conn = get_connection()
    try:
        if filter_name:
            rows = conn.execute(
                "SELECT * FROM transactions WHERE from_name = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (filter_name, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def count_transactions(filter_name=None):
    conn = get_connection()
    try:
        if filter_name:
            row = conn.execute("SELECT COUNT(*) as cnt FROM transactions WHERE from_name = ?", (filter_name,)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as cnt FROM transactions").fetchone()
        return row["cnt"]
    finally:
        conn.close()


def get_transaction_by_hash(tx_hash):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM transactions WHERE tx_hash LIKE ?", (f"%{tx_hash}%",)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_wallet_cache(name, address, balance, balance_usd, network_type="ETH"):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO wallet_cache (address, name, balance_eth, balance_usd, network_type, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(address) DO UPDATE SET balance_eth=?, balance_usd=?, updated_at=CURRENT_TIMESTAMP""",
            (address, name, balance, balance_usd, network_type, balance, balance_usd),
        )
        conn.commit()
    finally:
        conn.close()


def get_wallet_caches(network_type=None):
    conn = get_connection()
    try:
        if network_type:
            rows = conn.execute(
                "SELECT address, balance_eth, balance_usd, updated_at FROM wallet_cache WHERE network_type = ?",
                (network_type,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT address, balance_eth, balance_usd, updated_at FROM wallet_cache").fetchall()
        return {row["address"]: dict(row) for row in rows}
    finally:
        conn.close()
