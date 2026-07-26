import asyncio
import json
import uuid
import os
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from db.database import init_db, execute_query, list_accounts, get_active_account, set_active_account
from market_data import get_market_data_provider, price_cache
from llm.llm_service import process_chat, execute_actions
from schwab_service import schwab_service

load_dotenv()

app = FastAPI(title="FinAlly Backend")

market_provider = get_market_data_provider()

async def snapshot_task():
    while True:
        await asyncio.sleep(30)
        try:
            active = get_active_account()
            if not active: continue
            acct_id = active["id"]
            cash = active["cash_balance"]
            
            positions = execute_query("SELECT ticker, quantity FROM positions WHERE user_id = 'default' AND account_id = ?", (acct_id,))
            pos_value = 0
            for p in positions:
                ticker = p["ticker"]
                qty = p["quantity"]
                cp = price_cache.get(ticker)
                if cp:
                    pos_value += cp["price"] * qty
                    
            total_value = cash + pos_value
            execute_query(
                "INSERT INTO portfolio_snapshots (id, user_id, account_id, total_value, recorded_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), "default", acct_id, total_value, datetime.utcnow().isoformat())
            )
        except Exception as e:
            print("Snapshot error", e)

@app.on_event("startup")
async def startup_event():
    init_db()
    
    # Sync Schwab accounts if available
    schwab_accts = schwab_service.get_linked_accounts()
    if schwab_accts:
        now = datetime.utcnow().isoformat()
        for idx, sa in enumerate(schwab_accts):
            execute_query("""
            INSERT INTO accounts (id, user_id, account_number, account_hash, name, type, is_active, cash_balance, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET account_hash=excluded.account_hash, cash_balance=excluded.cash_balance
            """, (sa["id"], "default", sa["account_number"], sa["account_hash"], sa["name"], sa["type"], 1 if idx == 0 else 0, sa["cash_balance"], now))

    # Get active watchlist tickers
    active = get_active_account()
    acct_id = active["id"] if active else "default"
    watchlist = execute_query("SELECT ticker FROM watchlist WHERE user_id = 'default' AND account_id = ?", (acct_id,))
    tickers = [row["ticker"] for row in watchlist]
    if not tickers:
        tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]
    market_provider.start(tickers)
    
    asyncio.create_task(snapshot_task())
    
@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/schwab/auth-status")
def schwab_auth_status():
    status = schwab_service.get_token_status()
    return status

@app.get("/api/schwab/auth-url")
def schwab_auth_url():
    url = schwab_service.get_auth_url()
    return {"auth_url": url}

@app.post("/api/schwab/disconnect")
def schwab_disconnect():
    schwab_service.disconnect()
    execute_query("UPDATE accounts SET is_active = 0 WHERE user_id = 'default'")
    return {"status": "disconnected"}

def render_schwab_success_page():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Schwab Authorization Successful</title>
        <style>
            body { background-color: #0d1117; color: #ffffff; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }
            .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 2rem; text-align: center; max-width: 400px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
            h2 { color: #2ea043; margin-top: 0; }
            p { color: #8b949e; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Schwab Connected!</h2>
            <p>Your authentication tokens have been updated successfully.</p>
            <p>You can close this window and return to FinAlly workstation.</p>
        </div>
        <script>
            if (window.opener) {
                try { window.opener.postMessage("schwab-auth-success", "*"); } catch(e) {}
                setTimeout(() => window.close(), 2500);
            }
        </script>
    </body>
    </html>
    """

@app.get("/api/schwab/callback")
def schwab_callback(code: str = Query(None), session: str = Query(None)):
    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")
    schwab_service.exchange_code_for_tokens(code)
    return HTMLResponse(content=render_schwab_success_page())

@app.get("/")
def root(code: str = Query(None), session: str = Query(None)):
    if code:
        schwab_service.exchange_code_for_tokens(code)
        return HTMLResponse(content=render_schwab_success_page())
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"status": "ok"}

@app.get("/api/accounts")
def get_accounts():
    accounts = list_accounts()
    is_mock = os.getenv("LLM_MOCK", "false").lower() == "true"
    schwab_connected = schwab_service.get_token_status().get("authenticated", False)
    
    if schwab_connected:
        schwab_accts = [a for a in accounts if a["type"] == "SCHWAB"]
        if not schwab_accts:
            new_sa = schwab_service.get_linked_accounts()
            if new_sa:
                now = datetime.utcnow().isoformat()
                for idx, sa in enumerate(new_sa):
                    execute_query("""
                    INSERT INTO accounts (id, user_id, account_number, account_hash, name, type, is_active, cash_balance, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET account_hash=excluded.account_hash, cash_balance=excluded.cash_balance
                    """, (sa["id"], "default", sa["account_number"], sa["account_hash"], sa["name"], sa["type"], 1 if idx == 0 else 0, sa["cash_balance"], now))
                accounts = list_accounts()
                schwab_accts = [a for a in accounts if a["type"] == "SCHWAB"]
                
        if schwab_accts:
            if not any(a.get("is_active") == 1 for a in schwab_accts):
                active_id = schwab_accts[0]["id"]
                set_active_account(active_id)
                for sa in schwab_accts:
                    sa["is_active"] = 1 if sa["id"] == active_id else 0
            return schwab_accts
            
    if not is_mock:
        return []
        
    return accounts

@app.get("/api/accounts/active")
def active_account():
    acct = get_active_account()
    if not acct:
        raise HTTPException(status_code=404, detail="No active account found")
    return acct

class AccountSelectRequest(BaseModel):
    account_id: str

@app.post("/api/accounts/select")
def select_account(req: AccountSelectRequest):
    updated = set_active_account(req.account_id)
    return updated

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
    is_mock = os.getenv("LLM_MOCK", "false").lower() == "true"
    schwab_connected = schwab_service.get_token_status().get("authenticated", False)
    
    if not schwab_connected and not is_mock:
        return {
            "account": None,
            "cash_balance": 0.0,
            "positions": [],
            "total_value": 0.0,
            "total_pnl": 0.0
        }

    active = get_active_account()
    acct_id = active["id"] if active else "default"
    acct_hash = active.get("account_hash") if active else None
    cash = active["cash_balance"] if active else 10000.0
    
    # Query live cash balance from Schwab if authenticated
    if acct_hash and schwab_service.client:
        try:
            details = schwab_service.get_account_details(acct_hash)
            if details and "securitiesAccount" in details:
                balances = details.get("securitiesAccount", {}).get("currentBalances", {})
                if "cashBalance" in balances:
                    cash = balances["cashBalance"]
                    execute_query("UPDATE accounts SET cash_balance = ? WHERE id = ?", (cash, acct_id))
        except Exception as e:
            print(f"[WARN] Failed to fetch live Schwab balances: {e}")

    positions = execute_query("SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = 'default' AND account_id = ?", (acct_id,))
    if not positions and acct_id == "acct_roth":
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

@app.post("/api/portfolio/trade")
def trade(req: TradeRequest):
    active = get_active_account()
    acct_hash = active.get("account_hash") if active else None
    
    if acct_hash and not os.getenv("LLM_MOCK", "false").lower() == "true":
        res = schwab_service.place_market_order(acct_hash, req.ticker, req.quantity, req.side)
        if not res.get("success"):
            print(f"[WARN] Schwab market order returned: {res}")
            
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
    active = get_active_account()
    acct_id = active["id"] if active else "default"
    snapshots = execute_query("SELECT total_value, recorded_at FROM portfolio_snapshots WHERE user_id = 'default' AND account_id = ? ORDER BY recorded_at ASC", (acct_id,))
    if not snapshots:
        snapshots = execute_query("SELECT total_value, recorded_at FROM portfolio_snapshots WHERE user_id = 'default' ORDER BY recorded_at ASC")
    return [{"total_value": s["total_value"], "recorded_at": s["recorded_at"]} for s in snapshots]

@app.get("/api/watchlist")
def get_watchlist():
    active = get_active_account()
    acct_id = active["id"] if active else "default"
    
    wl = execute_query("SELECT ticker FROM watchlist WHERE user_id = 'default' AND account_id = ?", (acct_id,))
    
    # If no custom watchlist exists for this active account yet, seed default starter tickers!
    if not wl:
        default_tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]
        now = datetime.utcnow().isoformat()
        for ticker in default_tickers:
            try:
                execute_query(
                    "INSERT INTO watchlist (id, user_id, account_id, ticker, added_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), "default", acct_id, ticker, now)
                )
            except Exception:
                pass
        wl = execute_query("SELECT ticker FROM watchlist WHERE user_id = 'default' AND account_id = ?", (acct_id,))
        
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
    active = get_active_account()
    acct_id = active["id"] if active else "default"
    execute_actions({
        "watchlist_changes": [{"ticker": req.ticker, "action": "add"}]
    }, account_id=acct_id)
    return {"status": "ok"}

@app.delete("/api/watchlist/{ticker}")
def remove_watchlist(ticker: str):
    active = get_active_account()
    acct_id = active["id"] if active else "default"
    execute_actions({
        "watchlist_changes": [{"ticker": ticker, "action": "remove"}]
    }, account_id=acct_id)
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
