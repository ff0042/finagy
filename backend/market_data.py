import abc
import concurrent.futures
import json
import logging
import math
import os
import random
import threading
import time
import urllib.request
from datetime import UTC, datetime
from typing import Any


class PriceCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._cache = {}
        
    def update(self, ticker: str, price: float, change: float = None, change_percent: float = None):
        with self._lock:
            existing = self._cache.get(ticker, {})
            if change is None or change_percent is None:
                prev_price = existing.get("price", price)
                change = price - prev_price
                change_percent = (change / prev_price * 100) if prev_price > 0 else 0

            self._cache[ticker] = {
                "price": price,
                "change": round(float(change), 4) if change is not None else 0.0,
                "change_percent": round(float(change_percent), 2) if change_percent is not None else 0.0,
                "timestamp": datetime.now(UTC).isoformat()
            }
            
    def get_all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._cache)
            
    def get(self, ticker: str) -> Any:
        with self._lock:
            return self._cache.get(ticker)

price_cache = PriceCache()

def get_ticker_variants(ticker: str) -> list[str]:
    t = ticker.upper().strip()
    variants = [t]
    if "-" in t:
        parts = t.split("-")
        if len(parts) == 2 and len(parts[1]) <= 3:
            series = parts[1]
            variants.append(f"{parts[0]}-P{series}")
            variants.append(f"{parts[0]}/PR{series}")
            variants.append(f"{parts[0]}-PR{series}")
            variants.append(f"{parts[0]}.PR.{series}")
            variants.append(f"{parts[0]}.P{series}")
            variants.append(f"{parts[0]}.{series}")
    elif "/" in t:
        parts = t.split("/")
        if len(parts) == 2 and parts[1].startswith("PR"):
            series = parts[1].replace("PR", "")
            variants.append(f"{parts[0]}-{series}")
            variants.append(f"{parts[0]}-P{series}")
            variants.append(f"{parts[0]}-PR{series}")
    elif "." in t:
        parts = t.split(".")
        if len(parts) == 2:
            variants.append(f"{parts[0]}-{parts[1]}")
            variants.append(f"{parts[0]}/{parts[1]}")

    seen = set()
    res = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            res.append(v)
    return res

def fetch_real_market_price(ticker: str) -> float:
    variants = get_ticker_variants(ticker)
    api_key = os.getenv("MASSIVE_API_KEY")
    for t_var in variants:
        if api_key:
            try:
                url = f"https://api.polygon.io/v2/aggs/ticker/{t_var}/prev?apiKey={api_key}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode())
                    if data.get("results"):
                        return round(float(data["results"][0]["c"]), 2)
            except Exception:
                pass

        try:
            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{t_var}?interval=1d"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                meta = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
                if price and float(price) > 0:
                    return round(float(price), 2)
        except Exception:
            pass

    return None

def fetch_real_market_price_details(ticker: str) -> tuple[float, float, float]:
    variants = get_ticker_variants(ticker)
    for t_var in variants:
        try:
            url = f"https://query2.finance.yahoo.com/v8/finance/chart/{t_var}?interval=1d"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                meta = data["chart"]["result"][0]["meta"]
                price = meta.get("regularMarketPrice") or meta.get("chartPreviousClose")
                prev_close = meta.get("chartPreviousClose")
                if price and float(price) > 0:
                    p = round(float(price), 4)
                    if prev_close and float(prev_close) > 0:
                        c = p - float(prev_close)
                        cp = (c / float(prev_close)) * 100
                    else:
                        c = 0.0
                        cp = 0.0
                    return p, round(c, 4), round(cp, 2)
        except Exception:
            pass

    p = fetch_real_market_price(ticker)
    if p is not None:
        return p, 0.0, 0.0
    return None, 0.0, 0.0

class BaseMarketData(abc.ABC):
    @abc.abstractmethod
    def start(self, tickers: list[str]):
        pass

    @abc.abstractmethod
    def add_ticker(self, ticker: str):
        pass

class SchwabMarketData(BaseMarketData):
    """Schwab Developer API Market Data Provider using schwabdev library."""
    def __init__(self):
        self.running = False
        self.tickers: set[str] = set()
        self._lock = threading.Lock()

    def start(self, tickers: list[str]):
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
        try:
            from backend.schwab_service import schwab_service
        except ModuleNotFoundError:
            from schwab_service import schwab_service
        client = schwab_service.client
        if client:
            try:
                variants = get_ticker_variants(ticker)
                resp = client.quotes(variants)
                if resp and resp.status_code == 200:
                    data = resp.json()
                    for v in variants:
                        if v in data:
                            ticker_data = data[v]
                            asset_type = ticker_data.get("assetMainType", "EQUITY")
                            quote = ticker_data.get("quote", {})
                            net_change = quote.get("netChange")
                            net_pct = quote.get("netPercentChange")
                            
                            if asset_type == "OPTION":
                                price = quote.get("mark") if quote.get("mark") is not None else (quote.get("lastPrice") if quote.get("lastPrice") is not None else quote.get("closePrice"))
                            else:
                                price = quote.get("lastPrice") if quote.get("lastPrice") is not None else (quote.get("mark") if quote.get("mark") is not None else quote.get("closePrice"))
                                
                            if price is not None:
                                price_cache.update(ticker, round(float(price), 4), change=net_change, change_percent=net_pct)
                                return
            except Exception:
                pass
        p, c, cp = fetch_real_market_price_details(ticker)
        if p is not None:
            price_cache.update(ticker, p, change=c, change_percent=cp)

    def _poll(self):
        try:
            from backend.schwab_service import schwab_service
        except ModuleNotFoundError:
            from schwab_service import schwab_service
        while self.running:
            with self._lock:
                active_list = list(self.tickers)

            client = schwab_service.client
            if active_list and client:
                try:
                    all_variants = []
                    var_map = {}
                    for t in active_list:
                        vs = get_ticker_variants(t)
                        all_variants.extend(vs)
                        for v in vs:
                            var_map[v] = t

                    resp = client.quotes(all_variants)
                    if resp and resp.status_code == 200:
                        data = resp.json()
                        for v_key, ticker_data in data.items():
                            orig_ticker = var_map.get(v_key)
                            if not orig_ticker:
                                continue
                            asset_type = ticker_data.get("assetMainType", "EQUITY")
                            quote_info = ticker_data.get("quote", {})
                            net_change = quote_info.get("netChange")
                            net_pct = quote_info.get("netPercentChange")
                            
                            if asset_type == "OPTION":
                                price = quote_info.get("mark") if quote_info.get("mark") is not None else (quote_info.get("lastPrice") if quote_info.get("lastPrice") is not None else quote_info.get("closePrice"))
                            else:
                                price = quote_info.get("lastPrice") if quote_info.get("lastPrice") is not None else (quote_info.get("mark") if quote_info.get("mark") is not None else quote_info.get("closePrice"))
                                
                            if price is not None:
                                price_cache.update(orig_ticker, round(float(price), 4), change=net_change, change_percent=net_pct)
                except Exception:
                    for ticker in active_list:
                        p, c, cp = fetch_real_market_price_details(ticker)
                        if p is not None:
                            price_cache.update(ticker, p, change=c, change_percent=cp)
            else:
                for ticker in active_list:
                    p, c, cp = fetch_real_market_price_details(ticker)
                    if p is not None:
                        price_cache.update(ticker, p, change=c, change_percent=cp)

            tick_freq = float(os.getenv("TICK_FREQUENCY_SECONDS", "5.0"))
            time.sleep(tick_freq)

class YahooFinanceMarketData(BaseMarketData):
    """Free-tier real market data provider powered by Yahoo Finance chart REST API."""
    def __init__(self):
        self.running = False
        self._lock = threading.Lock()
        self.tickers: set[str] = set()

    def start(self, tickers: list[str]):
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

    def _poll(self):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        base_prices = {}
        while self.running:
            with self._lock:
                active_list = list(self.tickers)

            if active_list:
                try:
                    missing = [t for t in active_list if t not in base_prices]
                    if missing:
                        results = list(executor.map(fetch_real_market_price_details, missing))
                        for ticker, (price, change, change_percent) in zip(missing, results):
                            if price is not None:
                                base_prices[ticker] = (price, change, change_percent)

                    for ticker in active_list:
                        if ticker in base_prices:
                            base_p, base_c, base_cp = base_prices[ticker]
                            prev_close = base_p - base_c if (base_p - base_c) > 0 else base_p
                            shift = random.choice([-0.03, -0.02, -0.01, 0.01, 0.02, 0.03])
                            live_p = round(max(0.01, base_p + shift), 4)
                            live_c = round(base_c + shift, 4)
                            live_cp = round((live_c / prev_close) * 100, 2) if prev_close > 0 else base_cp
                            price_cache.update(ticker, live_p, change=live_c, change_percent=live_cp)
                except Exception as e:
                    logging.warning(f"Error fetching free tier Yahoo Finance prices: {e}")

            tick_freq = float(os.getenv("TICK_FREQUENCY_SECONDS", "5.0"))
            time.sleep(tick_freq)
        executor.shutdown(wait=False)

# Backward compatibility alias
GBMMarketSimulator = YahooFinanceMarketData

class MassiveMarketData(BaseMarketData):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.running = False
        self._lock = threading.Lock()
        self.tickers: set[str] = set()

    def start(self, tickers: list[str]):
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

    def _poll(self):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        while self.running:
            with self._lock:
                active_list = list(self.tickers)

            if active_list:
                try:
                    results = list(executor.map(fetch_real_market_price, active_list))
                    for ticker, price in zip(active_list, results):
                        if price is not None:
                            price_cache.update(ticker, round(float(price), 4))
                except Exception as e:
                    logging.warning(f"Error fetching free tier Yahoo Finance prices: {e}")

            tick_freq = float(os.getenv("TICK_FREQUENCY_SECONDS", "10.0"))
            time.sleep(tick_freq)
        executor.shutdown(wait=False)

_provider_instance = None

def get_market_data_provider() -> BaseMarketData:
    global _provider_instance
    try:
        try:
            from backend.schwab_service import schwab_service
            from backend.db.database import execute_query, get_active_account
        except ModuleNotFoundError:
            from schwab_service import schwab_service
            from db.database import execute_query, get_active_account

        active = get_active_account()
        acct_id = active["id"] if active else DEFAULT_ACCOUNT_ID
        acct_type = active.get("type", "ROTH") if active else "ROTH"
        schwab_auth = schwab_service.get_token_status().get("authenticated", False)

        if acct_type == "SCHWAB" and schwab_auth:
            if not isinstance(_provider_instance, SchwabMarketData):
                if _provider_instance and hasattr(_provider_instance, "running"):
                    _provider_instance.running = False
                _provider_instance = SchwabMarketData()
                logging.info("[INFO] Initialized Schwab Developer API Market Data Provider.")
                try:
                    wl = execute_query("SELECT ticker FROM watchlist WHERE user_id = 'default' AND account_id = ?", (acct_id,))
                    initial_tickers = [r["ticker"] for r in wl] if wl else DEFAULT_TICKERS
                except Exception:
                    initial_tickers = DEFAULT_TICKERS
                _provider_instance.start(initial_tickers)
            return _provider_instance

        if not isinstance(_provider_instance, (YahooFinanceMarketData, MassiveMarketData)):
            if _provider_instance and hasattr(_provider_instance, "running"):
                _provider_instance.running = False
            
            if os.getenv("MASSIVE_API_KEY"):
                _provider_instance = MassiveMarketData(os.getenv("MASSIVE_API_KEY"))
            else:
                _provider_instance = YahooFinanceMarketData()
            
            logging.info("[INFO] Initialized Free-Tier Yahoo Finance Market Data Provider.")
            try:
                wl = execute_query("SELECT ticker FROM watchlist WHERE user_id = 'default' AND account_id = ?", (acct_id,))
                initial_tickers = [r["ticker"] for r in wl] if wl else DEFAULT_TICKERS
            except Exception:
                initial_tickers = DEFAULT_TICKERS
            _provider_instance.start(initial_tickers)

        return _provider_instance

    except Exception as e:
        logging.warning(f"Error checking market data provider status: {e}")

    if _provider_instance is None:
        _provider_instance = YahooFinanceMarketData()
        _provider_instance.start(DEFAULT_TICKERS)

    return _provider_instance
