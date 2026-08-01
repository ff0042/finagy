import json
from unittest.mock import MagicMock, patch

from backend.llm.llm_service import process_chat


def test_openrouter_model_selection(monkeypatch):
    """Test that process_chat uses the specified OPENROUTER_MODEL from env."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-3.1-pro-preview")
    monkeypatch.setenv("LLM_MOCK", "false")
    
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "message": "Processed with Gemini 3.1 Pro",
        "trades": [],
        "watchlist_changes": []
    })
    mock_response.choices[0].message.tool_calls = None
    
    with patch("backend.llm.llm_service.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response
        
        process_chat("what is my cash balance?", {"cash_balance": 10000.0}, [])
        
        # Verify OpenAI client was initialized with OpenRouter base URL
        mock_openai_cls.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-test-key"
        )
        # Verify model parameter passed to completions
        mock_client.chat.completions.create.assert_called_once()
        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["model"] == "google/gemini-3.1-pro-preview"

def test_openrouter_error_graceful_fallback(monkeypatch):
    """Test that if OpenRouter API encounters an error, it returns an informative error message and 0 orders."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-3.1-pro-preview")
    monkeypatch.setenv("LLM_MOCK", "false")
    
    with patch("backend.llm.llm_service.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("OpenRouter 500 Service Unavailable")
        
        res = process_chat("buy 5 shares of AAPL", {"cash_balance": 10000.0}, [])
        assert "AI Service Error" in res["message"]
        assert len(res.get("orders", [])) == 0

def test_llm_model_selection_endpoints():
    """Test GET /api/llm/models and POST /api/llm/model endpoints."""
    from backend.main import app
    from fastapi.testclient import TestClient
    tc = TestClient(app)
    
    res = tc.get("/api/llm/models")
    assert res.status_code == 200
    data = res.json()
    assert "active_model" in data
    assert "models" in data
    from backend.llm.llm_service import AVAILABLE_MODELS
    assert len(data["models"]) == len(AVAILABLE_MODELS)
    assert data["models"][0]["id"] == "mock/deterministic"
    assert data["models"][0]["cost_tier"] == "FREE"

def test_deterministic_free_model_behavior(monkeypatch):
    """Test that mock/deterministic model handles mechanical commands and advises model switch for complex queries, sell all, or short sales."""
    monkeypatch.setenv("OPENROUTER_MODEL", "mock/deterministic")
    
    # Test mechanical order execution
    res1 = process_chat("buy 10 shares of AAPL", {"cash_balance": 10000.0}, [])
    assert len(res1["orders"]) == 1
    assert res1["orders"][0]["ticker"] == "AAPL"
    assert res1["orders"][0]["quantity"] == 10
    
    # Test complex/strategy queries fallback
    res3 = process_chat("What happens to stocks if inflation rises?", {"cash_balance": 10000.0}, [])
    assert len(res3["orders"]) == 0
    assert "deterministic" in res3["message"].lower() or "smarter model" in res3["message"].lower()

    # Test short sale fallback (selling without position)
    res5 = process_chat("sell 10 shares of TSLA", {"cash_balance": 10000.0}, [])
    assert len(res5["orders"]) == 0
    assert "deterministic" in res5["message"].lower() or "smarter model" in res5["message"].lower()


def test_confirmation_mode_does_not_auto_extract_orders(monkeypatch):
    """Test that in confirmation mode, when model returns empty orders asking for confirmation, auto-extraction is bypassed."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
    monkeypatch.setenv("LLM_MOCK", "false")
    
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "message": "Submitting a GTC order to buy 10 shares of IBIT at $32.50 limit. Please reply with CONFIRMED to submit this order.",
        "orders": [],
        "watchlist_changes": []
    })
    mock_response.choices[0].message.tool_calls = None

    with patch("backend.llm.llm_service.OpenAI") as mock_openai_cls, \
          patch("backend.llm.llm_service.get_active_account", return_value={"id": "schwab_1", "type": "SCHWAB", "account_hash": "hash123"}), \
          patch("backend.llm.llm_service.get_autonomous_mode", return_value=False), \
          patch("backend.llm.llm_service.execute_actions") as mock_exec:
        
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response
        mock_exec.return_value = {"executed_orders": [], "failed_orders": []}
        
        res = process_chat("please buy 10 shares of ibit GTC at 32.5", {"cash_balance": 10000.0}, [])
        
        # Verify no orders were attached to response_data prior to confirmation
        assert len(res.get("orders", [])) == 0
        # Verify execute_actions was called with payload containing 0 orders
        assert mock_exec.call_count == 1
        executed_payload = mock_exec.call_args[0][0]
        assert len(executed_payload.get("orders", [])) == 0


def test_strict_case_sensitive_confirmation_guard(monkeypatch):
    """Test that in confirmation mode, lowercase 'confirmed' is rejected and 0 orders are executed."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
    monkeypatch.setenv("LLM_MOCK", "false")
    
    mock_response = MagicMock()
    # Simulate an LLM that prematurely outputted orders on lowercase 'confirmed'
    mock_response.choices[0].message.content = json.dumps({
        "message": "Order successfully cancelled.",
        "orders": [{"action": "cancel", "order_id": "12345", "ticker": "META"}],
        "watchlist_changes": []
    })
    mock_response.choices[0].message.tool_calls = None

    with patch("backend.llm.llm_service.OpenAI") as mock_openai_cls, \
          patch("backend.llm.llm_service.get_active_account", return_value={"id": "schwab_1", "type": "SCHWAB", "account_hash": "hash123"}), \
          patch("backend.llm.llm_service.get_autonomous_mode", return_value=False), \
          patch("backend.llm.llm_service.execute_actions") as mock_exec:
        
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response
        mock_exec.return_value = {"executed_orders": [], "failed_orders": []}
        
        # Test lowercase 'confirmed' -> Should be rejected by backend guard
        res = process_chat("confirmed", {"cash_balance": 10000.0}, [])
        assert "Confirmation Rejected" in res["message"]
        assert len(res.get("orders", [])) == 0
        
        # Test exact all-caps 'CONFIRMED' -> Should pass backend guard
        res_caps = process_chat("CONFIRMED", {"cash_balance": 10000.0}, [])
        assert len(res_caps.get("orders", [])) == 1
