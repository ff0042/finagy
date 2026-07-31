
from datetime import UTC, datetime
import uuid
from fastapi import APIRouter
from pydantic import BaseModel

from backend.constants import DEFAULT_ACCOUNT_ID, DEFAULT_TICKERS, DEFAULT_USER_ID
from backend.db.database import execute_query, get_active_account
from backend.market_data import get_market_data_provider, price_cache
from backend.trade_service import execute_actions

router = APIRouter()

@router.get("/api/watchlist")
def get_watchlist():
    active = get_active_account()
    acct_id = active["id"] if active else DEFAULT_ACCOUNT_ID
    
    wl = execute_query("SELECT ticker FROM watchlist WHERE user_id = ? AND account_id = ? ORDER BY added_at ASC", (DEFAULT_USER_ID, acct_id))

    res = []
    for row in wl:
        ticker = row["ticker"]
        cp = price_cache.get(ticker)
        res.append({
            "ticker": ticker,
            "price_data": cp
        })
    return res

class WatchlistRequest(BaseModel):
    ticker: str

@router.post("/api/watchlist")
def add_watchlist(req: WatchlistRequest):
    active = get_active_account()
    acct_id = active["id"] if active else DEFAULT_ACCOUNT_ID
    execute_actions({
        "watchlist_changes": [{"ticker": req.ticker, "action": "add"}]
    }, account_id=acct_id)
    return {"status": "ok"}

@router.delete("/api/watchlist/{ticker}")
def remove_watchlist(ticker: str):
    active = get_active_account()
    acct_id = active["id"] if active else DEFAULT_ACCOUNT_ID
    execute_actions({
        "watchlist_changes": [{"ticker": ticker, "action": "remove"}]
    }, account_id=acct_id)
    return {"status": "ok"}
