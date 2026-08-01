import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.db.database import execute_query, get_active_account
from backend.market_data import fetch_real_market_price, price_cache
from backend.schwab_service import schwab_service
from backend.trade_service import execute_actions

router = APIRouter()
logger = logging.getLogger(__name__)

# Mapping from user-facing timing values to Schwab session/duration pairs
TIMING_MAP: dict[str, tuple[str, str]] = {
    "day": ("NORMAL", "DAY"),
    "day_ext": ("SEAMLESS", "DAY"),
    "gtc": ("NORMAL", "GOOD_TILL_CANCEL"),
    "gtc_ext": ("SEAMLESS", "GOOD_TILL_CANCEL"),
    "ext_am": ("AM", "DAY"),
    "ext_pm": ("PM", "DAY"),
}

VALID_ORDER_TYPES = {"market", "limit", "stop", "stop_limit", "market_on_close"}
VALID_ACTIONS = {"buy", "sell", "sell_short", "buy_to_cover"}
VALID_TIMINGS = set(TIMING_MAP.keys())


class OrderCreateRequest(BaseModel):
    ticker: str
    action: str
    quantity: int
    order_type: str = "market"
    price: float | None = None
    stop_price: float | None = None
    timing: str = "day"


class OrderCreateResponse(BaseModel):
    success: bool
    order_id: str | None = None
    message: str = ""
    error: str | None = None


def _get_current_price(ticker: str) -> float | None:
    """Get the current market price for a ticker from cache or real-time fetch."""
    cp = price_cache.get(ticker.upper())
    if cp and cp.get("price"):
        return cp["price"]
    return fetch_real_market_price(ticker.upper())


def _validate_order(req: OrderCreateRequest) -> list[str]:
    """Validate order request. Returns list of error messages (empty if valid)."""
    errors: list[str] = []

    if not req.ticker or not req.ticker.strip():
        errors.append("Ticker symbol is required.")

    action = req.action.lower().replace(' ', '_')
    if action not in VALID_ACTIONS:
        errors.append(f"Invalid action '{req.action}'. Must be one of: buy, sell, sell_short, buy_to_cover.")

    if req.quantity <= 0:
        errors.append("Quantity must be greater than 0.")

    order_type = req.order_type.lower().replace(' ', '_')
    if order_type not in VALID_ORDER_TYPES:
        errors.append(f"Invalid order type '{req.order_type}'. Must be one of: {', '.join(VALID_ORDER_TYPES)}.")

    timing = req.timing.lower().replace(' ', '_')
    if timing not in VALID_TIMINGS:
        errors.append(f"Invalid timing '{req.timing}'. Must be one of: {', '.join(VALID_TIMINGS)}.")

    # Price requirements based on order type
    if order_type in ("limit", "stop_limit") and req.price is None:
        errors.append(f"Limit price is required for {order_type} orders.")

    if order_type in ("stop", "stop_limit") and req.stop_price is None:
        errors.append(f"Stop price is required for {order_type} orders.")

    # Stop-limit specific validation
    if order_type == "stop_limit" and req.price is not None and req.stop_price is not None:
        current_price = _get_current_price(req.ticker)
        if current_price is not None:
            if action in ("buy", "buy_to_cover"):
                if req.stop_price <= current_price:
                    errors.append(
                        f"Stop-limit buy: Stop price (${req.stop_price:.2f}) must be above the current price (${current_price:.2f})."
                    )
                if req.price < req.stop_price:
                    errors.append(
                        f"Stop-limit buy: Limit price (${req.price:.2f}) must be above or equal to stop price (${req.stop_price:.2f})."
                    )
            elif action in ("sell", "sell_short"):
                if req.stop_price >= current_price:
                    errors.append(
                        f"Stop-limit sell: Stop price (${req.stop_price:.2f}) must be below the current price (${current_price:.2f})."
                    )
                if req.price > req.stop_price:
                    errors.append(
                        f"Stop-limit sell: Limit price (${req.price:.2f}) must be less than or equal to stop price (${req.stop_price:.2f})."
                    )

    return errors


def _format_schwab_orders(raw_orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format raw Schwab order data into a standardized order list."""
    formatted: list[dict[str, Any]] = []
    for order in raw_orders:
        status = order.get("status", "UNKNOWN").upper()
        # Include all working (open) and filled orders
        VALID_STATUSES = (
            "WORKING", "OPEN", "NEW", "FILLED", "QUEUED", "ACCEPTED",
            "PENDING_ACTIVATION", "AWAITING_PARENT_ORDER", "AWAITING_CONDITION",
            "PENDING_CANCEL", "PENDING_REPLACE"
        )
        if status not in VALID_STATUSES:
            continue

        order_type = order.get("orderType", "MARKET")
        session = order.get("session", "NORMAL")
        duration = order.get("duration", "DAY")
        
        # Reverse-map session/duration to user-facing timing
        timing = "day"
        for key, (s, d) in TIMING_MAP.items():
            if s == session and d == duration:
                timing = key
                break

        legs = order.get("orderLegCollection", [])
        ticker = ""
        action = ""
        quantity = 0
        asset_type = "EQUITY"
        description = ""
        if legs:
            leg = legs[0]
            instrument = leg.get("instrument", {})
            ticker = instrument.get("symbol", "")
            asset_type = instrument.get("assetType", "EQUITY")
            raw_instruction = leg.get("instruction", "BUY")
            action = raw_instruction.lower().replace('_', ' ')
            quantity = leg.get("quantity", 0)
            
            # For options, build a friendly description
            if asset_type == "OPTION":
                description = instrument.get("description", ticker)
            else:
                description = ticker

        # Get filled price from activities
        filled_price: float | None = None
        activities = order.get("orderActivityCollection", [])
        for activity in activities:
            exec_legs = activity.get("executionLegs", [])
            for el in exec_legs:
                filled_price = el.get("price")

        formatted.append({
            "order_id": str(order.get("orderId", "")),
            "ticker": ticker,
            "description": description,
            "action": action,
            "quantity": quantity,
            "order_type": order_type.lower().replace('_', ' '),
            "price": order.get("price"),
            "stop_price": order.get("stopPrice"),
            "filled_price": filled_price,
            "timing": timing,
            "status": "FILLED" if status == "FILLED" else "OPEN",
            "entered_time": order.get("enteredTime", ""),
        })
    return formatted


@router.get("/api/orders")
def get_orders() -> list[dict[str, Any]]:
    """Get open and filled orders for the active account."""
    active = get_active_account()
    if not active:
        return []

    schwab_connected = schwab_service.get_token_status().get("authenticated", False)
    acct_hash = active.get("account_hash")

    if schwab_connected and acct_hash:
        result = schwab_service.get_orders(acct_hash)
        if result.get("success") and result.get("orders"):
            return _format_schwab_orders(result["orders"])
        return []

    # Local paper trading: return orders from SQLite placed within the last week
    acct_id = active["id"]
    from datetime import timedelta
    cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    rows = execute_query(
        "SELECT id, ticker, side, quantity, order_type, limit_price, stop_price, "
        "time_in_force, status, created_at FROM orders "
        "WHERE user_id = 'default' AND account_id = ? AND status IN ('WORKING', 'FILLED') "
        "AND created_at >= ? "
        "ORDER BY created_at DESC",
        (acct_id, cutoff),
    )
    return [
        {
            "order_id": r["id"],
            "ticker": r["ticker"],
            "description": r["ticker"],
            "action": r["side"],
            "quantity": r["quantity"],
            "order_type": (r["order_type"] or "market").lower(),
            "price": r["limit_price"],
            "stop_price": r["stop_price"],
            "filled_price": None,
            "timing": (r["time_in_force"] or "day").lower(),
            "status": "FILLED" if r["status"] == "FILLED" else "OPEN",
            "entered_time": r["created_at"],
        }
        for r in rows
    ]


@router.post("/api/orders", response_model=OrderCreateResponse)
def create_order(req: OrderCreateRequest) -> OrderCreateResponse:
    """Validate and submit an order."""
    validation_errors = _validate_order(req)
    if validation_errors:
        raise HTTPException(status_code=400, detail="; ".join(validation_errors))

    order_type = req.order_type.lower().replace(' ', '_')
    action = req.action.lower().replace(' ', '_')
    timing = req.timing.lower().replace(' ', '_')
    session, duration = TIMING_MAP.get(timing, ("NORMAL", "DAY"))

    order_payload = {
        "orders": [{
            "action": "submit",
            "ticker": req.ticker.upper(),
            "side": action,
            "quantity": req.quantity,
            "order_type": order_type,
            "limit_price": req.price,
            "stop_price": req.stop_price,
            "time_in_force": duration.lower(),
            "session": session,
        }]
    }

    result = execute_actions(order_payload)
    executed = result.get("executed_orders", [])
    failed = result.get("failed_orders", [])

    if executed:
        return OrderCreateResponse(
            success=True,
            message=f"Order submitted: {action.replace('_', ' ')} {req.quantity} {req.ticker.upper()}"
        )

    error_detail = "; ".join(failed) if failed else "Order submission failed"
    return OrderCreateResponse(success=False, error=error_detail)


@router.delete("/api/orders/{order_id}")
def cancel_order(order_id: str) -> dict[str, Any]:
    """Cancel an open order. No confirmation required."""
    active = get_active_account()
    if not active:
        raise HTTPException(status_code=404, detail="No active account")

    schwab_connected = schwab_service.get_token_status().get("authenticated", False)
    acct_hash = active.get("account_hash")

    if schwab_connected and acct_hash:
        result = schwab_service.cancel_order(acct_hash, order_id)
        if result.get("success"):
            return {"status": "ok", "message": f"Order {order_id} cancelled"}
        raise HTTPException(
            status_code=400,
            detail=result.get("text", result.get("error", "Cancel failed"))
        )

    # Local cancel
    execute_query(
        "UPDATE orders SET status = 'CANCELED', updated_at = ? WHERE id = ?",
        (datetime.now(UTC).isoformat(), order_id)
    )
    return {"status": "ok", "message": f"Order {order_id} cancelled"}
