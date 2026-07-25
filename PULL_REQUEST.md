# Pull Request: feat(v3): Multi-Account Selection & Schwab Developer API Integration

## 📌 Title
`feat(v3): Multi-Account Selection & Schwab Developer API Integration`

---

## 📋 Executive Summary
This Pull Request introduces **V3 Multi-Account Selection** for Finagy/FinAlly. Users can now view, select, and switch between multiple trading accounts (e.g., `ROTH_IRA`, `TRADING_MAIN`, `TAXABLE_ACCOUNT`, or live linked Schwab accounts) directly from the workstation header. All portfolio balances, stock positions, treemap heatmaps, PnL historical charts, and quick market trade executions (`buy`/`sell`) are dynamically scoped to the selected active account.

---

## 🏗️ Technical Architecture & Detailed Changes

### 1. Database Schema & Auto-Migrations (`backend/db/database.py`)
* **`accounts` Table**:
  * Fields: `id` (PRIMARY KEY), `user_id`, `account_number`, `account_hash`, `name`, `type`, `is_active` (0/1), `cash_balance`, `created_at`.
  * Seeded default mock accounts for offline testing (`ROTH_IRA` [$10,000], `TRADING_MAIN` [$25,000], `TAXABLE_ACCOUNT` [$50,000]).
* **Column Auto-Migrations**:
  * Automatically applies `ALTER TABLE ... ADD COLUMN account_id` to existing SQLite tables (`watchlist`, `positions`, `trades`, `portfolio_snapshots`) for backward compatibility.
* **Account State Helpers**:
  * `list_accounts()`: Retrieves all available user accounts.
  * `get_active_account()`: Fetches the currently selected account (`is_active = 1`).
  * `set_active_account(account_id)`: Atomically updates active account selection.

### 2. Schwab Developer API Multi-Account Wrapper (`backend/schwab_service.py`)
* **`SchwabService` Class**:
  * High-level service wrapper using `schwabdev v3.0.5`.
  * `get_linked_accounts()`: Invokes `client.account_linked()` to retrieve account numbers and `hashValue` keys.
  * `get_account_details(account_hash)`: Queries live balances and equity/options positions via `client.account_details()`.
  * `place_market_order(...)`: Formats and submits equity market orders (`BUY`/`SELL`) against the active `account_hash`.

### 3. REST API Endpoint Expansion (`backend/main.py`)
* **Account Management Endpoints**:
  * `GET /api/accounts`: Returns list of available accounts for dropdown selector.
  * `GET /api/accounts/active`: Returns details of currently active account.
  * `POST /api/accounts/select`: Sets active account (`{"account_id": "acct_roth"}`).
* **Account Scoping**:
  * `GET /api/portfolio`: Dynamically computes cash, positions, and total value for the active `account_id`.
  * `POST /api/portfolio/trade`: Routes order execution to `schwab_service.place_market_order()` using active `account_hash`.
  * `GET /api/portfolio/history`: Filters snapshot history by active `account_id`.

### 4. Frontend Account Selector Component (`frontend/src/components/AccountSelector.tsx` & `Header.tsx`)
* **`AccountSelector.tsx`**:
  * Reusable UI dropdown displaying account name, masked account number (`***5131`), account type (`ROTH`/`INDIVIDUAL`), and cash balance.
  * On selection, posts to `/api/accounts/select` and dispatches custom `refresh-workstation` event.
* **`Header.tsx`**:
  * Integrated `AccountSelector` into workstation navigation bar.

---

## 📡 API Specification

### `GET /api/accounts`
* **Response**: `200 OK`
  ```json
  [
    {
      "id": "acct_roth",
      "account_number": "56515131",
      "account_hash": "hash_roth_56515131",
      "name": "ROTH_IRA",
      "type": "ROTH",
      "is_active": 1,
      "cash_balance": 10000.0
    },
    {
      "id": "acct_trading",
      "account_number": "88421092",
      "account_hash": "hash_trading_88421092",
      "name": "TRADING_MAIN",
      "type": "INDIVIDUAL",
      "is_active": 0,
      "cash_balance": 25000.0
    }
  ]
  ```

### `POST /api/accounts/select`
* **Request Body**:
  ```json
  { "account_id": "acct_trading" }
  ```
* **Response**: `200 OK` returning updated active account dictionary.

---

## 🧪 Verification & Test Results

### Automated Unit Tests (`backend/tests/test_backend.py`)
* Executed Pytest suite using `uv run --python 3.11 python -m pytest`.
* **Result**: **`7 passed in 1.47s`** (added `test_accounts_api` for account listing and active selection).

### Frontend Build
* Built static export using `npm run build` in `frontend/`.
* Next.js static pages generated cleanly (`4/4 static pages prerendered`).

### Docker Single-Container Verification
* Rebuilt and verified Docker image running live on `http://localhost:8000/`.

---

## 🔒 Security Verification
* Ran local pre-commit secret scanner script (`scripts/secret_scan.py`).
* **Result**: `[SUCCESS] No sensitive secrets or personal designators detected in staged files.`

---

## 🚀 Known Limitations & Next Steps (V3.1 / V4)
* **OAuth2 Authentication Flow**: Schwab API refresh tokens require periodic browser OAuth re-authorization. The next task (V3.1) will implement automated OAuth PKCE callback handling and token refresh flows.
* **Options Desk**: Subsequent release (V4) will add options chain visualization and multi-leg order execution.
