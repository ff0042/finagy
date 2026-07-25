import os
import pytest
from fastapi.testclient import TestClient

# Set mock environment for tests before importing main
os.environ["LLM_MOCK"] = "true"

from main import app
from db.database import init_db, execute_query, DB_PATH
from market_data import price_cache

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    # Reset table contents for test isolation
    for table in ["chat_messages", "portfolio_snapshots", "trades", "positions", "watchlist", "users_profile", "accounts"]:
        execute_query(f"DELETE FROM {table}")
    init_db()
    yield

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_db_lazy_init():
    user = execute_query("SELECT cash_balance FROM users_profile WHERE id = 'default'")
    assert len(user) == 1
    assert user[0]["cash_balance"] == 10000.0

def test_accounts_api():
    response = client.get("/api/accounts")
    assert response.status_code == 200
    accounts = response.json()
    assert len(accounts) >= 3
    names = [a["name"] for a in accounts]
    assert "ROTH_IRA" in names
    assert "TRADING_MAIN" in names
    
    # Active account
    response = client.get("/api/accounts/active")
    assert response.status_code == 200
    active = response.json()
    assert active["name"] == "ROTH_IRA"
    
    # Switch account
    trading_acct = next(a for a in accounts if a["name"] == "TRADING_MAIN")
    response = client.post("/api/accounts/select", json={"account_id": trading_acct["id"]})
    assert response.status_code == 200
    assert response.json()["name"] == "TRADING_MAIN"
    
    # Verify active account switched
    response = client.get("/api/accounts/active")
    assert response.json()["name"] == "TRADING_MAIN"

def test_portfolio_empty():
    response = client.get("/api/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert data["cash_balance"] == 10000.0

def test_trading_logic():
    # Setup mock price
    price_cache.update("AAPL", 150.0)
    
    # Buy
    response = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    assert response.status_code == 200
    
    portfolio = client.get("/api/portfolio").json()
    assert portfolio["cash_balance"] == 8500.0 # 10000 - (150 * 10)
    assert len(portfolio["positions"]) == 1
    assert portfolio["positions"][0]["ticker"] == "AAPL"
    assert portfolio["positions"][0]["quantity"] == 10
    
    # Sell
    response = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "sell"})
    assert response.status_code == 200
    
    portfolio = client.get("/api/portfolio").json()
    assert portfolio["cash_balance"] == 9250.0 # 8500 + (150 * 5)
    assert portfolio["positions"][0]["quantity"] == 5

def test_watchlist():
    response = client.get("/api/watchlist")
    assert response.status_code == 200
    tickers = [item["ticker"] for item in response.json()]
    assert "AAPL" in tickers
    assert "GOOGL" in tickers
    
    # Add
    client.post("/api/watchlist", json={"ticker": "PYPL"})
    response = client.get("/api/watchlist")
    tickers = [item["ticker"] for item in response.json()]
    assert "PYPL" in tickers
    
    # Remove
    client.delete("/api/watchlist/PYPL")
    response = client.get("/api/watchlist")
    tickers = [item["ticker"] for item in response.json()]
    assert "PYPL" not in tickers

def test_chat_mock():
    response = client.post("/api/chat", json={"message": "Buy 10 AAPL"})
    assert response.status_code == 200
    data = response.json()
    assert "Executed purchase of 10 share(s) of AAPL" in data["message"]
    assert len(data["trades"]) == 1
    assert data["trades"][0]["ticker"] == "AAPL"
    assert data["trades"][0]["side"] == "buy"
    assert data["trades"][0]["quantity"] == 10
