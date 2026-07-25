# Pull Request: feat(v2): Schwab Developer API Market Data Provider Integration (schwabdev v3.0.5)

## 📌 Title
`feat(v2): Schwab Developer API Market Data Provider Integration (schwabdev v3.0.5)`

---

## 📝 Summary & Rationale
This Pull Request introduces **V2 Schwab Developer API Market Data Integration** for Finagy/FinAlly. When `LLM_MOCK=false` and Schwab Developer API credentials are provided, the backend seamlessly routes price streaming through official Schwab Market Data quotes endpoints via the latest **`schwabdev v3.0.5`** PyPI package.

---

## 🛠️ Key Changes

### 1. Market Data Engine (`backend/market_data.py`)
* **`SchwabMarketData` Provider Class**:
  * Initializes `schwabdev.Client` using `SCHWAB_CLIENT_ID`, `SCHWAB_CLIENT_SECRET`, and `SCHWAB_REDIRECT_URI`.
  * Auto-discovers and manages OAuth2 refresh tokens in `db/tokens.json` (with fallback discovery for local development token files).
  * Polls live market quotes (`client.quotes(tickers)`) on a 2-second interval, populating active price caches.
  * Includes automated fallback to `fetch_real_market_price(ticker)` if Schwab API tokens require re-authorization or encounter network delays.
* **Provider Factory (`get_market_data_provider`)**:
  * Dynamically instantiates `SchwabMarketData` when `LLM_MOCK=false` and Schwab credentials are present.

### 2. Dependencies & Runtime (`backend/pyproject.toml` & `uv.lock`)
* Added `schwabdev>=3.0.5` dependency.
* Updated `requires-python` requirement to `>=3.11` as mandated by `schwabdev v3.x`.

### 3. Environment & Documentation (`.env.example`)
* Added Schwab Developer credential configurations to `.env.example`:
  ```env
  SCHWAB_CLIENT_ID=your-schwab-client-id-here
  SCHWAB_CLIENT_SECRET=your-schwab-client-secret-here
  SCHWAB_REDIRECT_URI=https://127.0.0.1:8080
  SCHWAB_TOKENS_FILE=db/tokens.json
  ```

---

## 🧪 Testing & Verification

* **Unit Tests**: Executed Pytest suite using `uv run --python 3.11 python -m pytest`.
  * Result: **`6 passed in 1.87s`**.
* **Container Build**: Built and verified single-container Docker image serving pre-compiled Next.js 14 frontend and FastAPI backend.
* **SSE Price Streaming**: Verified live `/api/watchlist` and `/api/stream/prices` endpoints streaming real-time prices.

---

## 🚀 How to Test / Review

1. Pull the branch: `git checkout feature/v2-schwab-market-data`
2. Update `.env` with your Schwab Developer credentials or set `LLM_MOCK=false`.
3. Launch container: `.\scripts\start_windows.ps1`
4. Access workstation at `http://localhost:8000/`.
