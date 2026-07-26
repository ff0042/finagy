# FinAlly — Regression & Integration Test Ledger

This ledger tracks all regression and integration tests added for interactive bug fixes, security enhancements, and new major feature additions.

---

## Suite Summary & Quick Run Command

To run the entire backend test suite:
```powershell
$env:PYTHONPATH="."; uv run pytest
```

---

## Recorded Tests

### 1. Dynamic OpenRouter Model Selection & Graceful Fallback
* **Type**: Major Feature
* **Date Added**: 2026-07-26
* **Description**: Routes LLM chat requests to the specified `OPENROUTER_MODEL` via OpenRouter.ai, falling back gracefully to mock responses on API error or missing keys without requiring separate Google AI Studio keys.
* **Test File**: [test_llm_fallback.py](file:///c:/Users/ullul/PycharmProjects/finagy/backend/tests/test_llm_fallback.py)
* **Test Cases**:
  * `test_openrouter_model_selection`: Verifies `OPENROUTER_MODEL` environment variable (e.g. `google/gemini-3.1-pro-preview`) is passed to OpenRouter.
  * `test_openrouter_error_graceful_fallback`: Verifies graceful fallback to deterministic mock engine on OpenRouter errors.
  * `test_llm_model_selection_endpoints`: Verifies `GET /api/llm/models` listing and `POST /api/llm/model` interactive model switching.
  * `test_deterministic_free_model_behavior`: Verifies `mock/deterministic` FREE model executes mechanical trade & watchlist commands, and returns guidance for complex queries.

### 2. Multi-Account Selection & Schwab Integration
* **Type**: Milestone Feature
* **Date Added**: 2026-07-25
* **Description**: Enables switching between active accounts (ROTH IRA, Trading Main, etc.) and fetching account state.
* **Test File**: [test_backend.py](file:///c:/Users/ullul/PycharmProjects/finagy/backend/tests/test_backend.py#L42)
* **Test Cases**:
  * `test_accounts_api`: Verifies account list endpoints and active account retrieval.

### 3. Schwab OAuth PKCE Authentication & Hydration
* **Type**: Security & Integration Feature
* **Date Added**: 2026-07-25 (Updated 2026-07-26)
* **Description**: Complete OAuth PKCE authentication workflow and token persistence matching `schwabdev` schema (`access_token_issued`, `refresh_token_issued`, `token_dictionary`) for live balance hydration.
* **Test File**: [test_backend.py](file:///c:/Users/ullul/PycharmProjects/finagy/backend/tests/test_backend.py#L27)
* **Test Cases**:
  * `test_schwab_auth_endpoints`: Verifies auth status and auth URL generation endpoints.

### 4. Portfolio Trading Logic & Cash Management
* **Type**: Core Functionality
* **Date Added**: 2026-07-25
* **Description**: Market order execution, instant position updating, and cash balance deduction.
* **Test File**: [test_backend.py](file:///c:/Users/ullul/PycharmProjects/finagy/backend/tests/test_backend.py#L62)
* **Test Cases**:
  * `test_trading_logic`: Verifies stock purchases deduct cash and update positions correctly.

### 5. Account-Scoped Watchlist Persistence & LLM Mock Handling
* **Type**: Bug Fix & UI Polish
* **Date Added**: 2026-07-25
* **Description**: Scopes watchlists per account, handles LLM error fallbacks, and auto-focuses chat inputs.
* **Test File**: [test_backend.py](file:///c:/Users/ullul/PycharmProjects/finagy/backend/tests/test_backend.py#L37)
* **Test Cases**:
  * `test_db_lazy_init`: Verifies default user profile and database table initialization.

### 6. Ephemeral Session-Scoped Disconnected Baseline
* **Type**: Major Feature & Architecture Polish
* **Date Added**: 2026-07-26
* **Description**: Resets disconnected workstation state (Cash Balance = $10,000, Total Value = $10,000, Positions = [], Heatmap = [], Watchlist = 10 default tickers) whenever a new browser tab/session starts or after disconnecting from Schwab.
* **Test File**: [main.py](file:///c:/Users/ullul/PycharmProjects/finagy/backend/main.py#L88)
* **Test Cases**:
  * `POST /api/session/reset`: Resets active session state to clean initial baseline.

### 7. Disconnected Mode Model Locking (FREE Model Only)
* **Type**: Feature & UX Polish
* **Date Added**: 2026-07-26
* **Description**: Locks the AI model selector to `mock/deterministic` (FREE) when Schwab is disconnected. Greys out paid/smart models in the dropdown with a "Requires Schwab Connection" badge until Schwab is connected.
* **Test File**: [ModelSelector.tsx](file:///c:/Users/ullul/PycharmProjects/finagy/frontend/src/components/ModelSelector.tsx#L100)
* **Test Cases**:
  * Disconnected state automatically locks active model to `mock/deterministic` and disables non-free models.

### 8. Release v3.3 Codebase Cleanup & Single Source of Truth Isolation
* **Type**: Major Refactoring & Technical Debt Reduction
* **Date Added**: 2026-07-26
* **Description**: Extracted `execute_actions()` to `trade_service.py` to strictly enforce the Single Source of Truth rule (Schwab API only for Schwab accounts; DB transactions for local accounts). Modularized `main.py` into FastAPI routers (`routers/auth.py`, `routers/portfolio.py`, `routers/watchlist.py`, `routers/llm.py`). Created centralized constants (`constants.py`), types (`types/index.ts`), API wrapper (`lib/api.ts`), AuthContext (`AuthContext.tsx`), and event listener hook (`useWorkstationRefresh.ts`). Migrated FastAPI to `lifespan` context manager.
* **Test Files**: [test_trades.py](file:///c:/Users/ullul/PycharmProjects/finagy/backend/tests/test_trades.py), [test_backend.py](file:///c:/Users/ullul/PycharmProjects/finagy/backend/tests/test_backend.py), [test_llm_fallback.py](file:///c:/Users/ullul/PycharmProjects/finagy/backend/tests/test_llm_fallback.py)
* **Test Cases**:
  * `test_execute_actions_buy_sell_local`: Verifies local trade executions deduct cash and update positions atomically.
  * `test_execute_actions_insufficient_funds`: Verifies trade rejection when cash balance is lower than total purchase price.
  * `test_session_reset_endpoint`: Verifies `POST /api/session/reset` resets disconnected state cleanly.
