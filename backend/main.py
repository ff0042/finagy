import asyncio
import json
import uuid
import os
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from db.database import init_db, execute_query
from market_data import get_market_data_provider, price_cache
from llm.llm_service import process_chat, execute_actions

load_dotenv()

app = FastAPI(title="FinAlly Backend")

market_provider = get_market_data_provider()

async def snapshot_task():
    while True:
        await asyncio.sleep(30)
        try:
            # calculate total value
            user = execute_query("SELECT cash_balance FROM users_profile WHERE id = 'default'")
            if not user: continue
            cash = user[0]["cash_balance"]
            
            positions = execute_query("SELECT ticker, quantity FROM positions WHERE user_id = 'default'")
            pos_value = 0
            for p in positions:
                ticker = p["ticker"]
                qty = p["quantity"]
                cp = price_cache.get(ticker)
                if cp:
                    pos_value += cp["price"] * qty
                    
            total_value = cash + pos_value
            execute_query(
                "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), "default", total_value, datetime.utcnow().isoformat())
            )
        except Exception as e:
            print("Snapshot error", e)

@app.on_event("startup")
async def startup_event():
    init_db()
    # Get watchlist tickers
    watchlist = execute_query("SELECT ticker FROM watchlist WHERE user_id = 'default'")
    tickers = [row["ticker"] for row in watchlist]
    if not tickers:
        tickers = ["AAPL", "GOOGL", "MSFT"]
    market_provider.start(tickers)
    
    asyncio.create_task(snapshot_task())
    
@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/stream/prices")
async def stream_prices(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            prices = price_cache.get_all()
            yield f"data: {json.dumps(prices)}\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/portfolio")
def get_portfolio():
    user = execute_query("SELECT cash_balance FROM users_profile WHERE id = 'default'")[0]
    cash = user["cash_balance"]
    
    positions = execute_query("SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = 'default'")
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
        "cash_balance": cash,
        "positions": pos_list,
        "total_value": total_value,
        "total_pnl": total_pos_value - total_cost
    }

class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str

@app.post("/api/portfolio/trade")
def trade(req: TradeRequest):
    # Reuse execute_actions logic
    execute_actions({
        "trades": [{
            "ticker": req.ticker,
            "side": req.side,
            "quantity": req.quantity
        }]
    })
    return {"status": "ok"}

@app.get("/api/portfolio/history")
def get_history():
    snapshots = execute_query("SELECT total_value, recorded_at FROM portfolio_snapshots WHERE user_id = 'default' ORDER BY recorded_at ASC")
    return [{"total_value": s["total_value"], "recorded_at": s["recorded_at"]} for s in snapshots]

@app.get("/api/watchlist")
def get_watchlist():
    wl = execute_query("SELECT ticker FROM watchlist WHERE user_id = 'default'")
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

@app.post("/api/watchlist")
def add_watchlist(req: WatchlistRequest):
    execute_actions({
        "watchlist_changes": [{"ticker": req.ticker, "action": "add"}]
    })
    # Add to market provider if needed (simplification: assume handled or restart needed)
    return {"status": "ok"}

@app.delete("/api/watchlist/{ticker}")
def remove_watchlist(ticker: str):
    execute_actions({
        "watchlist_changes": [{"ticker": ticker, "action": "remove"}]
    })
    return {"status": "ok"}

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
def chat(req: ChatRequest):
    portfolio = get_portfolio()
    wl = get_watchlist()
    context = {
        "portfolio": portfolio,
        "watchlist": wl
    }
    
    history_rows = execute_query("SELECT role, content FROM chat_messages WHERE user_id = 'default' ORDER BY created_at DESC LIMIT 10")
    history = [{"role": r["role"], "content": r["content"]} for r in reversed(history_rows)]
    
    res = process_chat(req.message, context, history)
    return res

if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
elif os.path.exists("/app/static"):
    app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")

