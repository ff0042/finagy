import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure root and backend directory are in sys.path and load environment variables from .env
root_dir = Path(__file__).resolve().parent.parent
backend_dir = Path(__file__).resolve().parent
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Load .env file from root or backend directory
load_dotenv(root_dir / ".env")
load_dotenv(backend_dir / ".env")

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

try:
    from backend.constants import DEFAULT_ACCOUNT_ID, DEFAULT_TICKERS, DEFAULT_USER_ID
    from backend.db.database import execute_query, get_active_account, init_db
    from backend.market_data import get_market_data_provider
    from backend.routers import auth, llm, orders, portfolio, watchlist
    from backend.scheduler import start_scheduler
except ModuleNotFoundError:
    from constants import DEFAULT_ACCOUNT_ID, DEFAULT_TICKERS, DEFAULT_USER_ID
    from db.database import execute_query, get_active_account, init_db
    from market_data import get_market_data_provider
    from routers import auth, llm, orders, portfolio, watchlist
    from scheduler import start_scheduler


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

async def snapshot_task():
    while True:
        try:
            active = get_active_account()
            acct_id = active["id"] if active else DEFAULT_ACCOUNT_ID
            
            loop = asyncio.get_running_loop()
            from backend.routers.portfolio import get_portfolio
            portfolio_data = await loop.run_in_executor(None, get_portfolio)
            total_value = portfolio_data.get("total_value", 10000.0)
            
            from backend.schwab_service import schwab_service
            schwab_connected = schwab_service.get_token_status().get("authenticated", False)
            if schwab_connected and active and active.get("type") == "SCHWAB":
                from backend.routers.portfolio import schwab_snapshots
                if acct_id not in schwab_snapshots:
                    schwab_snapshots[acct_id] = []
                schwab_snapshots[acct_id].append({
                    "total_value": total_value,
                    "recorded_at": datetime.now(UTC).isoformat()
                })
            else:
                execute_query(
                    "INSERT INTO portfolio_snapshots (id, user_id, account_id, total_value, recorded_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), DEFAULT_USER_ID, acct_id, total_value, datetime.now(UTC).isoformat())
                )
        except Exception as e:
            logger.error(f"Snapshot task error: {e}")
        await asyncio.sleep(30)

task_ref = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    def handle_exception(loop, context):
        exc = context.get("exception")
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError)) or (isinstance(exc, OSError) and getattr(exc, "winerror", None) == 10054):
            return
        loop.default_exception_handler(context)
    loop.set_exception_handler(handle_exception)

    logger.info("Initializing database...")
    init_db()
    
    # Start APScheduler
    start_scheduler()
    
    logger.info("Starting market data provider...")
    market_provider = get_market_data_provider()
    from backend.schwab_service import schwab_service
    if schwab_service.get_token_status().get("authenticated", False):
        initial_tickers = []
    else:
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
app.include_router(orders.router)


@app.get('/api/health')
def health():
    return {'status': 'ok'}

from fastapi import Request


@app.get("/")
def read_root(request: Request):
    if request.query_params.get("code") or request.query_params.get("error"):
        return auth.schwab_callback(request)
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    elif os.path.exists("/app/static/index.html"):
        return FileResponse("/app/static/index.html")
    return {"message": "FinAlly API is running. Frontend not found in static folder."}

if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
elif os.path.exists("/app/static"):
    app.mount("/", StaticFiles(directory="/app/static", html=True), name="static")
