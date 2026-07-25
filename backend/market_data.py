import abc
import os
import threading
import time
import math
import random
import urllib.request
import json
import concurrent.futures
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Set

class PriceCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._cache = {}
        
    def update(self, ticker: str, price: float):
        with self._lock:
            prev_price = self._cache.get(ticker, {}).get("price", price)
            change = price - prev_price
            change_percent = (change / prev_price * 100) if prev_price > 0 else 0
            self._cache[ticker] = {
                "price": price,
                "prev_price": prev_price,
                "change": change,
                "change_percent": change_percent,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    def get_all(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._cache)
            
    def get(self, ticker: str) -> Any:
        with self._lock:
            return self._cache.get(ticker)

price_cache = PriceCache()

def fetch_real_market_price(ticker: str) -> float:
    ticker_clean = ticker.upper().strip()
    
    # 1. Try Polygon/Massive API if key set
    api_key = os.getenv("MASSIVE_API_KEY")
    if api_key:
        try:
            url = f"https://api.polygon.io/v2/aggs/ticker/{ticker_clean}/prev?apiKey={api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                if data.get("results"):
                    return round(float(data["results"][0]["c"]), 2)
        except Exception:
            pass

    # 2. Try Yahoo Finance chart REST API (Free real market data)
    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker_clean}?interval=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
            if price and float(price) > 0:
                return round(float(price), 2)
    except Exception:
        pass

    # 3. Fallback deterministic fallback based on ticker hash if network is unavailable
    seed = sum(ord(c) for c in ticker_clean) * 17 % 450 + 20
    return round(float(seed), 2)

class BaseMarketData(abc.ABC):
    @abc.abstractmethod
    def start(self, tickers: List[str]):
        pass

    @abc.abstractmethod
    def add_ticker(self, ticker: str):
        pass

class SchwabMarketData(BaseMarketData):
    """Schwab Developer API Market Data Provider using schwabdev library."""
    def __init__(self):
        self.running = False
        self.tickers: Set[str] = set()
        self._lock = threading.Lock()
        self.client = None
        self._init_client()

    def _init_client(self):
        app_key = os.getenv("SCHWAB_CLIENT_ID") or os.getenv("SCHWAB_APP_KEY")
        app_secret = os.getenv("SCHWAB_CLIENT_SECRET") or os.getenv("SCHWAB_APP_SECRET")
        callback_url = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1:8080")
        tokens_db = os.getenv("SCHWAB_TOKENS_DB", "db/tokens.db")

        if not app_key or not app_secret:
            raise ValueError("Schwab API credentials missing (SCHWAB_CLIENT_ID / SCHWAB_CLIENT_SECRET)")

        tokens_path = Path(tokens_db)
        tokens_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import schwabdev
            self.client = schwabdev.Client(
                app_key=app_key,
                app_secret=app_secret,
                callback_url=callback_url,
                tokens_db=str(tokens_path)
            )
        except Exception as e:
            print(f"[WARN] schwabdev client initialization error: {e}")
            self.client = None

    def start(self, tickers: List[str]):
        with self._lock:
            self.tickers = set(t.upper() for t in tickers)
        self.running = True
        self.thread = threading.Thread(target=self._poll, daemon=True)
        self.thread.start()

    def add_ticker(self, ticker: str):
        ticker = ticker.upper()
        with self._lock:
            if ticker not in self.tickers:
                self.tickers.add(ticker)
                threading.Thread(target=self._fetch_single_quote, args=(ticker,), daemon=True).start()

    def _fetch_single_quote(self, ticker: str):
        if self.client:
            try:
                resp = self.client.quotes([ticker])
                if resp and resp.status_code == 200:
                    data = resp.json()
                    quote = data.get(ticker, {}).get("quote", {})
                    price = quote.get("lastPrice") or quote.get("mark")
                    if price:
                        price_cache.update(ticker, round(float(price), 2))
                        return
            except Exception:
                pass
        price = fetch_real_market_price(ticker)
        price_cache.update(ticker, price)

    def _poll(self):
        while self.running:
            with self._lock:
                active_list = list(self.tickers)

            if active_list and self.client:
                try:
                    resp = self.client.quotes(active_list)
                    if resp and resp.status_code == 200:
                        data = resp.json()
                        for ticker in active_list:
                            quote_info = data.get(ticker, {}).get("quote", {})
                            price = quote_info.get("lastPrice") or quote_info.get("mark")
                            if price:
                                price_cache.update(ticker, round(float(price), 2))
                except Exception:
                    for ticker in active_list:
                        cp = price_cache.get(ticker)
                        current = cp["price"] if cp else fetch_real_market_price(ticker)
                        price_cache.update(ticker, round(current, 2))
            else:
                for ticker in active_list:
                    price = fetch_real_market_price(ticker)
                    price_cache.update(ticker, price)

            time.sleep(2.0)

class GBMMarketSimulator(BaseMarketData):
    def __init__(self):
        self.running = False
        self._lock = threading.Lock()
        self.tickers: Set[str] = set()
        
    def start(self, tickers: List[str]):
        with self._lock:
            self.tickers = set(t.upper() for t in tickers)
        self.running = True
        self.thread = threading.Thread(target=self._simulate, daemon=True)
        self.thread.start()

    def add_ticker(self, ticker: str):
        ticker = ticker.upper()
        with self._lock:
            if ticker not in self.tickers:
                self.tickers.add(ticker)
                threading.Thread(target=self._init_ticker_price, args=(ticker,), daemon=True).start()

    def _init_ticker_price(self, ticker: str):
        real_price = fetch_real_market_price(ticker)
        price_cache.update(ticker, real_price)

    def _simulate(self):
        with self._lock:
            current_tickers = list(self.tickers)

        # Concurrently resolve real prices for initial tickers
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(self._init_ticker_price, current_tickers)
            
        dt = 0.5 / (252 * 24 * 60 * 60) # roughly 500ms step
        mu = 0.05
        sigma = 0.2
        
        while self.running:
            sector_shock = random.gauss(0, 0.01)
            with self._lock:
                active_list = list(self.tickers)

            for ticker in active_list:
                cp = price_cache.get(ticker)
                if not cp:
                    price = fetch_real_market_price(ticker)
                    price_cache.update(ticker, price)
                    current = price
                else:
                    current = cp["price"]

                shock = random.gauss(0, 1) + sector_shock
                drift = (mu - 0.5 * sigma**2) * dt
                volatility = sigma * math.sqrt(dt) * shock
                new_price = max(0.01, current * math.exp(drift + volatility))
                price_cache.update(ticker, round(new_price, 2))
                
            time.sleep(0.5)

class MassiveMarketData(BaseMarketData):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.running = False
        self.tickers: Set[str] = set()
        self._lock = threading.Lock()
        
    def start(self, tickers: List[str]):
        with self._lock:
            self.tickers = set(t.upper() for t in tickers)
        self.running = True
        self.thread = threading.Thread(target=self._poll, daemon=True)
        self.thread.start()

    def add_ticker(self, ticker: str):
        ticker = ticker.upper()
        with self._lock:
            if ticker not in self.tickers:
                self.tickers.add(ticker)
                price = fetch_real_market_price(ticker)
                price_cache.update(ticker, price)
        
    def _poll(self):
        with self._lock:
            active_list = list(self.tickers)
        for ticker in active_list:
            price = fetch_real_market_price(ticker)
            price_cache.update(ticker, price)
        while self.running:
            with self._lock:
                active_list = list(self.tickers)
            for ticker in active_list:
                cp = price_cache.get(ticker)
                current = cp["price"] if cp else fetch_real_market_price(ticker)
                new_price = current * (1 + random.uniform(-0.005, 0.005))
                price_cache.update(ticker, round(new_price, 2))
            time.sleep(5.0)

_provider_instance = None

def get_market_data_provider() -> BaseMarketData:
    global _provider_instance
    if _provider_instance is None:
        mock_mode = os.getenv("LLM_MOCK", "false").lower() == "true"
        schwab_key = os.getenv("SCHWAB_CLIENT_ID") or os.getenv("SCHWAB_APP_KEY")
        
        # When LLM_MOCK is false and Schwab key is available, use Schwab Developer API
        if not mock_mode and schwab_key:
            try:
                _provider_instance = SchwabMarketData()
                print("[INFO] Initialized Schwab Developer API Market Data Provider.")
            except Exception as e:
                print(f"[WARN] Failed to initialize Schwab Market Data ({e}). Falling back to live simulator.")
                _provider_instance = GBMMarketSimulator()
        elif os.getenv("MASSIVE_API_KEY"):
            _provider_instance = MassiveMarketData(os.getenv("MASSIVE_API_KEY"))
        else:
            _provider_instance = GBMMarketSimulator()
    return _provider_instance
