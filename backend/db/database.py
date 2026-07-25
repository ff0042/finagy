import sqlite3
import os
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(r"c:\Users\ullul\PycharmProjects\finagy\db\finally.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    # Lazy initialization
    os.makedirs(DB_PATH.parent, exist_ok=True)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Create tables
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
        
        # Seed user
        cursor.execute("SELECT id FROM users_profile WHERE id = 'default'")
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
                ("default", 10000.0, datetime.utcnow().isoformat())
            )
            
            # Seed watchlist
            default_tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]
            for ticker in default_tickers:
                cursor.execute(
                    "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), "default", ticker, datetime.utcnow().isoformat())
                )
        
        conn.commit()

# Helper methods to interact with DB
def execute_query(query, params=()):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.fetchall()
