import asyncio
import json
import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.constants import DEFAULT_ACCOUNT_ID, DEFAULT_USER_ID
from backend.db.database import (
    execute_query,
    get_active_account,
    list_accounts,
    set_active_account,
)
from backend.market_data import get_market_data_provider, price_cache
from backend.schwab_service import schwab_service
from backend.trade_service import execute_actions

router = APIRouter()
logger = logging.getLogger(__name__)

schwab_snapshots = {}

def parse_occ_symbol(symbol: str) -> str:
    if len(symbol) < 21:
        return symbol
    root = symbol[:6].strip()
    yymmdd = symbol[6:12]
    cp = symbol[12:13]
    strike_str = symbol[13:]
    try:
        month_str = yymmdd[2:4]
        day_str = yymmdd[4:6]
        year_str = yymmdd[0:2]
        date_str = f"{month_str}/{day_str}/{year_str}"
        strike = float(strike_str) / 1000.0
        strike_fmt = f"{strike:g}"
        return f"{root} {date_str} {strike_fmt} {cp}"
    except Exception:  # noqa: BLE001
        return symbol

@router.get("/api/accounts")
def get_accounts():
    schwab_connected = schwab_service.get_token_status().get("authenticated", False)
    if schwab_connected:
        return schwab_service.get_linked_accounts()
            
    all_accts = list_accounts()
    local_accts = [a for a in all_accts if a.get("type") != "SCHWAB"]
    if local_accts and not any(a.get("is_active") == 1 for a in local_accts):
        set_active_account(local_accts[0]["id"])
        local_accts = [a for a in list_accounts() if a.get("type") != "SCHWAB"]
    return local_accts

class AccountSelectRequest(BaseModel):
    account_id: str

@router.post("/api/accounts/select")
def select_account(req: AccountSelectRequest):
    schwab_connected = schwab_service.get_token_status().get("authenticated", False)
    if schwab_connected and req.account_id.startswith("schwab_"):
        schwab_service.active_account_id = req.account_id
        schwab_service._linked_accts_cache = None
        return get_active_account()
    return set_active_account(req.account_id)

@router.get("/api/stream/prices")
async def stream_prices(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            prices = price_cache.get_all()
            yield f"data: {json.dumps(prices)}\n\n"
            tick_freq = float(os.getenv("TICK_FREQUENCY_SECONDS", "5.0"))
            await asyncio.sleep(tick_freq)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/api/portfolio")
def get_portfolio():
    schwab_connected = schwab_service.get_token_status().get("authenticated", False)
    accounts = get_accounts()
    active = get_active_account()
    
    if (not active or not any(a["id"] == active["id"] for a in accounts)) and accounts:
        if schwab_connected:
            schwab_service.active_account_id = accounts[0]["id"]
            schwab_service._linked_accts_cache = None
            active = get_active_account()
        else:
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
                    
                if active:
                    active["cash_balance"] = cash
                schwab_positions = sec_acct.get("positions", [])
                pos_list = []
                total_pos_value = 0.0
                total_cost = 0.0
                
                for p in schwab_positions:
                    instrument = p.get("instrument", {})
                    ticker = instrument.get("symbol", "")
                    if not ticker or instrument.get("assetType") == "CASH_EQUIVALENT" or ticker == "MMDA1":
                        continue
                        
                    try:
                        get_market_data_provider().add_ticker(ticker)
                    except Exception:  # noqa: S110, BLE001
                        pass
                        
                    asset_type = instrument.get("assetType", "EQUITY")
                    if asset_type == "COLLECTIVE_INVESTMENT":
                        asset_type = "ETF"
                    description = ticker
                    if asset_type == "OPTION":
                        description = parse_occ_symbol(ticker)
                    elif asset_type == "MUTUAL_FUND":
                        description = instrument.get("description", ticker)
                        
                    long_qty = p.get("longQuantity", 0)
                    short_qty = p.get("shortQuantity", 0)
                    qty = long_qty - short_qty
                    
                    if qty == 0:
                        continue
                        
                    if asset_type == "OPTION":
                        if qty > 0:
                            avg = p.get("taxLotAverageLongPrice") if p.get("taxLotAverageLongPrice") is not None else p.get("averagePrice", 0.0)
                        else:
                            avg = p.get("taxLotAverageShortPrice") if p.get("taxLotAverageShortPrice") is not None else p.get("averagePrice", 0.0)
                    else:
                        if qty > 0:
                            avg = p.get("taxLotAverageLongPrice", p.get("averagePrice", 0.0))
                        else:
                            avg = p.get("averageShortPrice", p.get("averagePrice", 0.0))
                        
                    multiplier = 100 if asset_type == "OPTION" else 1

                    cp = price_cache.get(ticker)
                    if cp:
                        current_price = cp["price"]
                    else:
                        market_val = p.get("marketValue", 0.0)
                        current_price = market_val / (qty * multiplier) if qty != 0 else avg

                    raw_cost = avg * qty * multiplier
                    raw_market_val = current_price * qty * multiplier
                    raw_unrealized = raw_market_val - raw_cost

                    total_pos_value += raw_market_val
                    total_cost += raw_cost

                    pos_list.append({
                        "ticker": ticker,
                        "description": description,
                        "asset_type": asset_type,
                        "quantity": qty,
                        "avg_cost": avg,
                        "current_price": current_price,
                        "market_value": round(raw_market_val, 2),
                        "unrealized_pnl": round(raw_unrealized, 2),
                        "live_pricing": True
                    })

                return {
                    "account": active,
                    "provider": get_market_data_provider().__class__.__name__,
                    "cash_balance": round(cash, 2),
                    "positions": pos_list,
                    "total_value": round(cash + total_pos_value, 2),
                    "total_pnl": round(total_pos_value - total_cost, 2)
                }
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Error fetching Schwab portfolio: {e}")

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
        
        raw_val = current_price * qty
        raw_cost = avg * qty
        raw_unrealized = raw_val - raw_cost
        
        total_pos_value += raw_val
        total_cost += raw_cost
        
        pos_list.append({
            "ticker": ticker,
            "description": ticker,
            "asset_type": "EQUITY",
            "quantity": qty,
            "avg_cost": avg,
            "current_price": current_price,
            "market_value": round(raw_val, 2),
            "unrealized_pnl": round(raw_unrealized, 2)
        })
        
    total_value = cash + total_pos_value
    
    return {
        "account": active,
        "cash_balance": round(cash, 2),
        "positions": pos_list,
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pos_value - total_cost, 2)
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
    
    schwab_connected = schwab_service.get_token_status().get("authenticated", False)
    if schwab_connected and active and active.get("type") == "SCHWAB":
        return schwab_snapshots.get(acct_id, [])

    snapshots = execute_query("SELECT total_value, recorded_at FROM portfolio_snapshots WHERE user_id = ? AND account_id = ? ORDER BY recorded_at ASC", (DEFAULT_USER_ID, acct_id))
    return [{"total_value": s["total_value"], "recorded_at": s["recorded_at"]} for s in snapshots]

@router.get('/api/accounts/active')
def active_account():
    return get_active_account()
