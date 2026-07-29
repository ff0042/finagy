import uuid
from datetime import UTC, datetime

from backend.db.database import execute_query, reset_session_state
from backend.trade_service import execute_actions


def test_trade_sell():
    reset_session_state()
    # Seed a position
    execute_query(
        "INSERT INTO positions (id, user_id, account_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), "default", "acct_roth", "AAPL", 10.0, 150.0, datetime.now(UTC).isoformat())
    )
    # Perform sell
    execute_actions({
        "trades": [{"ticker": "AAPL", "side": "sell", "quantity": 5.0}]
    }, account_id="acct_roth")
    
    pos = execute_query("SELECT quantity FROM positions WHERE ticker = 'AAPL' AND account_id = 'acct_roth'")
    assert pos[0]["quantity"] == 5.0
    
def test_insufficient_funds():
    reset_session_state()
    execute_query("UPDATE accounts SET cash_balance = 100.0 WHERE id = 'acct_roth'")
    execute_actions({
        "trades": [{"ticker": "TSLA", "side": "buy", "quantity": 10.0}] # 10 * 150 = 1500 > 100
    }, account_id="acct_roth")
    
    pos = execute_query("SELECT quantity FROM positions WHERE ticker = 'TSLA' AND account_id = 'acct_roth'")
    assert len(pos) == 0

def test_session_reset():
    reset_session_state()
    execute_query(
        "INSERT INTO positions (id, user_id, account_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), "default", "acct_roth", "NVDA", 10.0, 150.0, datetime.now(UTC).isoformat())
    )
    reset_session_state("acct_roth")
    pos = execute_query("SELECT quantity FROM positions WHERE account_id = 'acct_roth'")
    assert len(pos) == 0
    cash = execute_query("SELECT cash_balance FROM accounts WHERE id = 'acct_roth'")
    assert cash[0]["cash_balance"] == 10000.0
