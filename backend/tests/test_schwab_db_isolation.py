from unittest.mock import MagicMock, patch

import pytest
from backend.db.database import execute_query, init_db
from backend.main import app
from backend.schwab_service import schwab_service
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def setup_db():
    schwab_service.disconnect()
    init_db()
    for table in ["chat_messages", "portfolio_snapshots", "trades", "positions", "watchlist", "users_profile", "accounts"]:
        execute_query(f"DELETE FROM {table}")
    init_db()
    yield
    schwab_service.disconnect()

def test_schwab_db_isolation():
    # Setup mock Schwab client
    mock_client = MagicMock()
    schwab_service.client = mock_client
    
    # Mock token status to show authenticated
    mock_status = {"authenticated": True, "account_count": 1, "status": "connected"}
    
    # Mock linked accounts and details
    mock_linked_accounts = [
        {
            "id": "schwab_fakehash",
            "account_number": "12345678",
            "account_hash": "fakehash",
            "name": "SCHWAB_ACCT_5678",
            "type": "SCHWAB",
            "is_active": 1,
            "cash_balance": 12345.67
        }
    ]
    
    mock_acct_detail = {
        "securitiesAccount": {
            "currentBalances": {
                "cashBalance": 12345.67
            },
            "positions": [
                {
                    "instrument": {
                        "symbol": "AAPL",
                        "assetType": "EQUITY"
                    },
                    "longQuantity": 10,
                    "taxLotAverageLongPrice": 150.0,
                    "marketValue": 1500.0
                }
            ]
        }
    }
    
    # Spy on execute_query to trace SQLite calls
    called_queries = []
    import backend.db.database as db
    original_execute_query = db.execute_query
    
    def spy_execute_query(query, params=()):
        called_queries.append((query, params))
        return original_execute_query(query, params)
        
    with patch.object(schwab_service, 'get_token_status', return_value=mock_status), \
         patch.object(schwab_service, 'get_linked_accounts', return_value=mock_linked_accounts), \
         patch.object(schwab_service, 'get_account_details', return_value=mock_acct_detail), \
         patch.object(schwab_service, 'place_order', return_value={"success": True, "order_id": "999888"}) as mock_place_order, \
         patch("backend.db.database.execute_query", side_effect=spy_execute_query), \
         patch("backend.routers.watchlist.execute_query", side_effect=spy_execute_query), \
         patch("backend.routers.portfolio.execute_query", side_effect=spy_execute_query), \
         patch("backend.routers.auth.execute_query", side_effect=spy_execute_query), \
         patch("backend.routers.llm.execute_query", side_effect=spy_execute_query), \
         patch("backend.llm.llm_service.execute_query", side_effect=spy_execute_query), \
         patch("backend.trade_service.execute_query", side_effect=spy_execute_query):
        
        # Set active account in memory
        schwab_service.active_account_id = "schwab_fakehash"
        tc = TestClient(app)
        
        # ----------------------------------------------------
        # Test 1: Fetch Accounts - should not hit local DB
        # ----------------------------------------------------
        res = tc.get("/api/accounts")
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["type"] == "SCHWAB"
        
        # ----------------------------------------------------
        # Test 2: Fetch Portfolio - should not hit local DB for positions/cash updates
        # ----------------------------------------------------
        res = tc.get("/api/portfolio")
        assert res.status_code == 200
        data = res.json()
        assert data["cash_balance"] == 12345.67
        assert len(data["positions"]) == 1
        assert data["positions"][0]["ticker"] == "AAPL"
        
        # ----------------------------------------------------
        # Test 3: Watchlist API - should return empty and not query local DB
        # ----------------------------------------------------
        res = tc.get("/api/watchlist")
        assert res.status_code == 200
        assert res.json() == []
        
        # Try adding to watchlist in Schwab mode - should do nothing and not hit DB
        res = tc.post("/api/watchlist", json={"ticker": "TSLA"})
        assert res.status_code == 200
        
        # ----------------------------------------------------
        # Test 4: Submit Order - should call Schwab API and not insert into SQLite orders table
        # ----------------------------------------------------
        res = tc.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "buy"})
        assert res.status_code == 200
        mock_place_order.assert_called_once_with("fakehash", "AAPL", 5, "buy", "market", None, None, "day")
        
        # ----------------------------------------------------
        # Test 5: Portfolio History - should return empty or in-memory, no SQLite SELECT on snapshots
        # ----------------------------------------------------
        res = tc.get("/api/portfolio/history")
        assert res.status_code == 200
        
        # ----------------------------------------------------
        # Assert Database Isolation
        # Verify that no queries target watchlist, positions, orders, trades, portfolio_snapshots
        # ----------------------------------------------------
        forbidden_tables = ["WATCHLIST", "POSITIONS", "ORDERS", "TRADES", "PORTFOLIO_SNAPSHOTS"]
        for q, p in called_queries:
            q_upper = q.upper()
            # Skip setup_db cleanups
            if "DELETE FROM" in q_upper:
                continue
            for tbl in forbidden_tables:
                assert tbl not in q_upper, f"Forbidden database table {tbl} accessed in query: {q}"
            if ("UPDATE ACCOUNTS" in q_upper) or ("INSERT INTO ACCOUNTS" in q_upper):
                raise AssertionError(f"Forbidden database write on accounts table: {q}" if "UPDATE ACCOUNTS" in q_upper else f"Forbidden database insert on accounts table: {q}")

        # ----------------------------------------------------
        # Test 6: Chat History Exception - Chat messages MUST write to SQLite database
        # ----------------------------------------------------
        called_queries.clear()
        res = tc.post("/api/chat", json={"message": "hello schwab assistant"})
        assert res.status_code == 200
        
        # Verify that chat_messages table WAS written to
        chat_writes = [q for q, p in called_queries if "INSERT INTO CHAT_MESSAGES" in q.upper()]
        assert len(chat_writes) >= 2, "Chat history writes were bypassed, violating the chat messages database exception"
