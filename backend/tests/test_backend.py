import os

import pytest
from fastapi.testclient import TestClient

# Set mock environment for tests before importing main
os.environ["LLM_MOCK"] = "true"

from backend.db.database import execute_query, init_db
from backend.main import app
from backend.market_data import price_cache

client = TestClient(app)

from backend.schwab_service import schwab_service


@pytest.fixture(autouse=True)
def setup_db():
    schwab_service.disconnect()
    init_db()
    for table in ["chat_messages", "portfolio_snapshots", "trades", "positions", "watchlist", "users_profile", "accounts"]:
        execute_query(f"DELETE FROM {table}")
    init_db()
    yield

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_schwab_auth_endpoints():
    response = client.get("/api/schwab/auth-status")
    assert response.status_code == 200
    data = response.json()
    assert "authenticated" in data
    
    response = client.get("/api/schwab/auth-url")
    assert response.status_code == 200
    assert "auth_url" in response.json()

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
    
    response = client.get("/api/accounts/active")
    assert response.status_code == 200
    active = response.json()
    assert active["name"] == "ROTH_IRA"

def test_portfolio_empty():
    response = client.get("/api/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert data["cash_balance"] == 10000.0

def test_trading_logic():
    price_cache.update("AAPL", 150.0)
    
    response = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "buy"})
    assert response.status_code == 200
    
    portfolio = client.get("/api/portfolio").json()
    assert portfolio["cash_balance"] == 8500.0
    assert len(portfolio["positions"]) == 1
    assert portfolio["positions"][0]["ticker"] == "AAPL"
    assert portfolio["positions"][0]["quantity"] == 10
