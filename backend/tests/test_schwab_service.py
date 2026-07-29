import pytest
from unittest.mock import MagicMock
from backend.schwab_service import schwab_service

def test_schwab_place_order_payloads():
    # Setup mock client to ensure NO real trades are placed
    mock_client = MagicMock()
    schwab_service.client = mock_client
    
    # Setup mock response simulating a successful order submission
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"Location": "https://api.schwabapi.com/v1/accounts/fake_hash/orders/123456789"}
    mock_response.json.return_value = {"status": "success"}
    mock_client.place_order.return_value = mock_response

    # --- Test 1: MARKET BUY ---
    res = schwab_service.place_order(
        account_hash="fake_hash",
        ticker="AAPL",
        quantity=10,
        side="buy",
        order_type="MARKET",
        duration="DAY"
    )
    
    assert res["success"] is True
    assert res["order_id"] == "123456789"
    
    mock_client.place_order.assert_called_once()
    args, _ = mock_client.place_order.call_args
    assert args[0] == "fake_hash"
    
    order_spec = args[1]
    assert order_spec["orderType"] == "MARKET"
    assert "price" not in order_spec
    assert "stopPrice" not in order_spec
    assert order_spec["duration"] == "DAY"
    assert order_spec["orderLegCollection"][0]["instruction"] == "BUY"
    assert order_spec["orderLegCollection"][0]["quantity"] == 10
    assert order_spec["orderLegCollection"][0]["instrument"]["symbol"] == "AAPL"

    # --- Test 2: LIMIT SELL ---
    mock_client.place_order.reset_mock()
    res = schwab_service.place_order(
        account_hash="fake_hash",
        ticker="MSFT",
        quantity=5,
        side="sell",
        order_type="LIMIT",
        limit_price=400.0,
        duration="GTC"
    )
    
    assert res["success"] is True
    mock_client.place_order.assert_called_once()
    args, _ = mock_client.place_order.call_args
    order_spec = args[1]
    
    assert order_spec["orderType"] == "LIMIT"
    assert order_spec["price"] == 400.0
    assert "stopPrice" not in order_spec
    assert order_spec["duration"] == "GTC"
    assert order_spec["orderLegCollection"][0]["instruction"] == "SELL"

    # --- Test 3: STOP_LIMIT BUY ---
    mock_client.place_order.reset_mock()
    res = schwab_service.place_order(
        account_hash="fake_hash",
        ticker="TSLA",
        quantity=2,
        side="buy",
        order_type="STOP_LIMIT",
        limit_price=210.0,
        stop_price=205.0,
        duration="DAY"
    )
    
    assert res["success"] is True
    mock_client.place_order.assert_called_once()
    args, _ = mock_client.place_order.call_args
    order_spec = args[1]
    
    assert order_spec["orderType"] == "STOP_LIMIT"
    assert order_spec["price"] == 210.0
    assert order_spec["stopPrice"] == 205.0
    assert order_spec["orderLegCollection"][0]["instruction"] == "BUY"

def test_schwab_cancel_order():
    mock_client = MagicMock()
    schwab_service.client = mock_client
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client.cancel_order.return_value = mock_response
    
    res = schwab_service.cancel_order("fake_hash", "987654321")
    
    assert res["success"] is True
    mock_client.cancel_order.assert_called_once_with("fake_hash", "987654321")
