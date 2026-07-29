import os
import json
import pytest
from unittest.mock import patch, MagicMock
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
    """Test that if OpenRouter API encounters an error, it gracefully falls back to deterministic mock response."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-3.1-pro-preview")
    monkeypatch.setenv("LLM_MOCK", "false")
    
    with patch("backend.llm.llm_service.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("OpenRouter 500 Service Unavailable")
        
        # Should not raise exception, falls back gracefully to mock response
        process_chat("buy 5 shares of AAPL", {"cash_balance": 10000.0}, [])

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
    assert len(data["models"]) == 7
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
