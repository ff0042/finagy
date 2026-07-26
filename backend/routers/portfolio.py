
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import asyncio
from backend.db.database import execute_query, get_active_account, set_active_account, list_accounts
from backend.market_data import price_cache
from backend.schwab_service import schwab_service
from backend.constants import DEFAULT_USER_ID, DEFAULT_ACCOUNT_ID
from backend.trade_service import execute_actions

router = APIRouter()

@router.get("/api/accounts")
def get_accounts():
    return list_accounts()

class AccountSelectRequest(BaseModel):
    account_id: str

@router.post("/api/accounts/select")
def select_account(req: AccountSelectRequest):
    return set_active_account(req.account_id)

@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            prices = price_cache.get_all()
            yield f"data: {json.dumps(prices)}\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/api/portfolio")
def get_portfolio():
    schwab_connected = schwab_service.get_token_status().get("authenticated", False)
    accounts = get_accounts()
    active = get_active_account()
    
    if not active or not any(a["id"] == active["id"] for a in accounts):
        if accounts:
            active = set_active_account(accounts[0]["id"])

    acct_id = active["id"] if active else DEFAULT_ACCOUNT_ID
    acct_hash = active.get("account_hash") if active else None
    cash = active["cash_balance"] if active else 10000.0
    
    if schwab_connected and acct_hash:
        try:
            details = schwab_service.get_account_details(acct_hash)
            if details and "securitiesAccount" in details:
                sec_acct = details.get("securitiesAccount", {})
                balances = sec_acct.get("currentBalances", {}) or sec_acct.get("initialBalances", {})
                if "cashBalance" in balances:
                    cash = float(balances["cashBalance"])
                elif "cashAvailableForTrading" in balances:
                    cash = float(balances["cashAvailableForTrading"])
                elif "liquidity" in balances:
                    cash = float(balances["liquidity"])
                    
                execute_query("UPDATE accounts SET cash_balance = ? WHERE id = ?", (cash, acct_id))
                if active:
                    active["cash_balance"] = cash
        except Exception:
            pass

        return {
            "account": active,
            "cash_balance": cash,
            "positions": [],
            "total_value": cash,
            "total_pnl": 0.0
        }

    if not cash or cash <= 0:
        cash = 10000.0

    positions = execute_query("SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND account_id = ?", (DEFAULT_USER_ID, acct_id))
        
    pos_list = []
    total_pos_value = 0
    total_cost = 0
    
    for p in positions:
        ticker = p["ticker"]
        qty = p["quantity"]
        avg = p["avg_cost"]
        
        cp = price_cache.get(ticker)
        current_price = cp["price"] if cp else avg
        
        val = current_price * qty
        cost = avg * qty
        unrealized = val - cost
        
        total_pos_value += val
        total_cost += cost
        
        pos_list.append({
            "ticker": ticker,
            "quantity": qty,
            "avg_cost": avg,
            "current_price": current_price,
            "market_value": val,
            "unrealized_pnl": unrealized
        })
        
    total_value = cash + total_pos_value
    
    return {
        "account": active,
        "cash_balance": cash,
        "positions": pos_list,
        "total_value": total_value,
        "total_pnl": total_pos_value - total_cost
    }

class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str

@router.post("/api/portfolio/trade")
def trade(req: TradeRequest):
    execute_actions({
        "trades": [{
            "ticker": req.ticker,
            "side": req.side,
            "quantity": req.quantity
        }]
    })
    return {"status": "ok"}

@router.get("/api/portfolio/history")
def get_history():
    active = get_active_account()
    acct_id = active["id"] if active else DEFAULT_ACCOUNT_ID
    snapshots = execute_query("SELECT total_value, recorded_at FROM portfolio_snapshots WHERE user_id = ? AND account_id = ? ORDER BY recorded_at ASC", (DEFAULT_USER_ID, acct_id))
    return [{"total_value": s["total_value"], "recorded_at": s["recorded_at"]} for s in snapshots]

@router.get('/api/accounts/active')
def active_account():
    return get_active_account()
