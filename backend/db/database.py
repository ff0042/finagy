import sqlite3
import os
import uuid
from datetime import datetime
from pathlib import Path

if os.path.exists("/app/db"):
    DB_DIR = Path("/app/db")
else:
    DB_DIR = Path(__file__).parent.parent.parent / "db"

DB_PATH = DB_DIR / "finally.db"

def get_connection():
    return sqlite3.connect(str(DB_PATH))

def init_db():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Accounts table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'default',
            account_number TEXT,
            account_hash TEXT,
            name TEXT,
            type TEXT,
            is_active INTEGER DEFAULT 0,
            cash_balance REAL DEFAULT 10000.0,
            created_at TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users_profile (
            id TEXT PRIMARY KEY,
            cash_balance REAL DEFAULT 10000.0,
            created_at TEXT
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            ticker TEXT,
            added_at TEXT,
            UNIQUE(user_id, ticker)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            ticker TEXT,
            quantity REAL,
            avg_cost REAL,
            updated_at TEXT,
            UNIQUE(user_id, ticker)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            ticker TEXT,
            side TEXT,
            quantity REAL,
            price REAL,
            executed_at TEXT
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            total_value REAL,
            recorded_at TEXT
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            role TEXT,
            content TEXT,
            actions TEXT,
            created_at TEXT
        )
        """)
        
        # Column auto-migrations
        for col_def in [
            ("watchlist", "account_id TEXT DEFAULT 'acct_roth'"),
            ("positions", "account_id TEXT DEFAULT 'acct_roth'"),
            ("trades", "account_id TEXT DEFAULT 'acct_roth'"),
            ("portfolio_snapshots", "account_id TEXT DEFAULT 'acct_roth'")
        ]:
            try:
                cursor.execute(f"ALTER TABLE {col_def[0]} ADD COLUMN {col_def[1]}")
            except Exception:
                pass

        # Seed default accounts if empty
        cursor.execute("SELECT COUNT(*) FROM accounts")
        if cursor.fetchone()[0] == 0:
            now = datetime.utcnow().isoformat()
            default_accounts = [
                ("acct_roth", "default", "56515131", "hash_roth_56515131", "ROTH_IRA", "ROTH", 1, 10000.0, now),
                ("acct_trading", "default", "88421092", "hash_trading_88421092", "TRADING_MAIN", "INDIVIDUAL", 0, 25000.0, now),
                ("acct_taxable", "default", "99234150", "hash_taxable_99234150", "TAXABLE_ACCOUNT", "MARGIN", 0, 50000.0, now),
            ]
            cursor.executemany(
                "INSERT INTO accounts (id, user_id, account_number, account_hash, name, type, is_active, cash_balance, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                default_accounts
            )

        # Seed user profile
        cursor.execute("SELECT id FROM users_profile WHERE id = 'default'")
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
                ("default", 10000.0, datetime.utcnow().isoformat())
            )
            
            # Seed default watchlist
            default_tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]
            for ticker in default_tickers:
                cursor.execute(
                    "INSERT INTO watchlist (id, user_id, account_id, ticker, added_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), "default", "acct_roth", ticker, datetime.utcnow().isoformat())
                )
        
        conn.commit()

def execute_query(query, params=()):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.fetchall()

def get_active_account():
    rows = execute_query("SELECT * FROM accounts WHERE is_active = 1 LIMIT 1")
    if rows:
        return dict(rows[0])
    rows = execute_query("SELECT * FROM accounts LIMIT 1")
    if rows:
        return dict(rows[0])
    return None

def set_active_account(account_id: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET is_active = 0")
        cursor.execute("UPDATE accounts SET is_active = 1 WHERE id = ?", (account_id,))
        conn.commit()
    return get_active_account()

def list_accounts():
    rows = execute_query("SELECT * FROM accounts ORDER BY is_active DESC, name ASC")
    return [dict(r) for r in rows]

def reset_session_state(account_id: str = None):
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        if account_id:
            cursor.execute("UPDATE accounts SET cash_balance = 10000.0 WHERE id = ?", (account_id,))
            cursor.execute("DELETE FROM positions WHERE account_id = ?", (account_id,))
            cursor.execute("DELETE FROM trades WHERE account_id = ?", (account_id,))
            cursor.execute("DELETE FROM portfolio_snapshots WHERE account_id = ?", (account_id,))
            cursor.execute("DELETE FROM watchlist WHERE account_id = ?", (account_id,))
            
            default_tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]
            for ticker in default_tickers:
                cursor.execute(
                    "INSERT INTO watchlist (id, user_id, account_id, ticker, added_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), "default", account_id, ticker, now)
                )
            cursor.execute("DELETE FROM chat_messages;")
        else:
            cursor.execute("UPDATE accounts SET cash_balance = 10000.0 WHERE type != 'SCHWAB'")
            cursor.execute("DELETE FROM positions WHERE account_id NOT IN (SELECT id FROM accounts WHERE type = 'SCHWAB')")
            cursor.execute("DELETE FROM trades WHERE account_id NOT IN (SELECT id FROM accounts WHERE type = 'SCHWAB')")
            cursor.execute("DELETE FROM portfolio_snapshots WHERE account_id NOT IN (SELECT id FROM accounts WHERE type = 'SCHWAB')")
            cursor.execute("DELETE FROM watchlist WHERE account_id NOT IN (SELECT id FROM accounts WHERE type = 'SCHWAB')")
            cursor.execute("DELETE FROM chat_messages;")
            
            default_tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]
            for ticker in default_tickers:
                cursor.execute(
                    "INSERT INTO watchlist (id, user_id, account_id, ticker, added_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), "default", "acct_roth", ticker, now)
                )
        conn.commit()
