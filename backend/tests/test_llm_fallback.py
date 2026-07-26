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
    assert len(data["models"]) == 6
    assert data["models"][0]["id"] == "mock/deterministic"
    assert data["models"][0]["cost_tier"] == "FREE"
    
    post_res = tc.post("/api/llm/model", json={"model": "mock/deterministic"})
    assert post_res.status_code == 200
    assert post_res.json()["active_model"] == "mock/deterministic"

def test_deterministic_free_model_behavior(monkeypatch):
    """Test that mock/deterministic model handles mechanical commands and advises model switch for complex queries, sell all, or short sales."""
    monkeypatch.setenv("OPENROUTER_MODEL", "mock/deterministic")
    
    # Test mechanical order execution
    res1 = process_chat("buy 10 shares of AAPL", {"cash_balance": 10000.0}, [])
    assert len(res1["trades"]) == 1
    assert res1["trades"][0]["ticker"] == "AAPL"
    assert res1["trades"][0]["quantity"] == 10
    
    # Test unsupported complex query advice
    res2 = process_chat("suggest an options strategy for IBIT", {"cash_balance": 10000.0}, [])
    assert "I don't know how to do that" in res2["message"]
    assert "smarter model" in res2["message"]

    # Test 'sell all positions' returns fallback guidance and does not create fake short trades
    res3 = process_chat("sell all positions", {"cash_balance": 10000.0}, [])
    assert len(res3["trades"]) == 0
    assert "I don't know how to do that" in res3["message"]

    # Test short sale rejection for unowned ticker
    res4 = process_chat("sell 5 shares of NVDA", {"cash_balance": 10000.0}, [])
    assert len(res4["trades"]) == 0
    assert "I don't know how to do that" in res4["message"]
