
import sys
from pathlib import Path

# Ensure root and backend directory are in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = Path(__file__).resolve().parent
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import asyncio
import logging
import uuid
from datetime import datetime, timezone

try:
    from backend.db.database import init_db, execute_query, get_active_account
    from backend.market_data import get_market_data_provider, price_cache
    from backend.schwab_service import schwab_service
    from backend.constants import DEFAULT_USER_ID, DEFAULT_ACCOUNT_ID
    from backend.routers import auth, portfolio, watchlist, llm
except ModuleNotFoundError:
    from db.database import init_db, execute_query, get_active_account
    from market_data import get_market_data_provider, price_cache
    from schwab_service import schwab_service
    from constants import DEFAULT_USER_ID, DEFAULT_ACCOUNT_ID
    from routers import auth, portfolio, watchlist, llm

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

async def snapshot_task():
    while True:
        try:
            active = get_active_account()
            acct_id = active["id"] if active else DEFAULT_ACCOUNT_ID
            
            # Simple portfolio total calculation
            cash = active["cash_balance"] if active else 10000.0
            positions = execute_query("SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? AND account_id = ?", (DEFAULT_USER_ID, acct_id))
            total_pos_value = 0
            for p in positions:
                cp = price_cache.get(p["ticker"])
                current_price = cp["price"] if cp else p["avg_cost"]
                total_pos_value += current_price * p["quantity"]
                
            total_value = cash + total_pos_value
            
            execute_query(
                "INSERT INTO portfolio_snapshots (id, user_id, account_id, total_value, recorded_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), DEFAULT_USER_ID, acct_id, total_value, datetime.now(timezone.utc).isoformat())
            )
        except Exception as e:
            logger.error(f"Snapshot task error: {e}")
        await asyncio.sleep(30)

task_ref = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    init_db()
    
    logger.info("Starting market data provider...")
    market_provider = get_market_data_provider()
    wl = execute_query("SELECT ticker FROM watchlist")
    initial_tickers = [r["ticker"] for r in wl] if wl else DEFAULT_TICKERS
    market_provider.start(initial_tickers)
        
    global task_ref
    task_ref = asyncio.create_task(snapshot_task())
    
    yield
    
    logger.info("Shutting down...")
    if task_ref:
        task_ref.cancel()
    # market_provider.stop() # Needs to be implemented if missing

app = FastAPI(title="FinAlly", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(watchlist.router)
app.include_router(llm.router)

@app.get('/api/health')
def health():
    return {'status': 'ok'}

@app.get("/")
def read_root():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    elif os.path.exists("/app/static/index.html"):
        return FileResponse("/app/static/index.html")
    return {"message": "FinAlly API is running. Frontend not found in static folder."}

if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
elif os.path.exists("/app/static"):
    app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")
