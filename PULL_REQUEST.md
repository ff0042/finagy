# refactor(v3.3): Release v3.3 Code Cleanup, Single Source of Truth Isolation, and CI Workflow

## Summary of Changes

This PR delivers **Release v3.3**, addressing technical debt, architectural SRP violations, and code quality improvements identified in `planning/CLAUDE_REVIEW_V33.md`.

---

### Key Architectural Enhancements & Refactoring

1. **Single Source of Truth (SSOT) Trade Engine (`trade_service.py`)**:
   - Extracted trade execution out of `llm_service.py` into a dedicated `trade_service.py`.
   - **Schwab Accounts**: Reads and writes balances, positions, and trades **strictly via the Schwab API**, eliminating dual-write conflicts to local SQLite tables.
   - **Local Accounts**: Wraps local database trades in atomic SQLite transactions (`with get_connection() as conn`).

2. **FastAPI Application Decomposition**:
   - Split monolithic `main.py` into modular FastAPI `APIRouter` sub-modules under `backend/routers/`:
     - `routers/auth.py`: Schwab OAuth PKCE login, callback, disconnect, and session reset handlers.
     - `routers/portfolio.py`: Account listing, portfolio balances, position history, and manual trade endpoints.
     - `routers/watchlist.py`: Watchlist additions and removals.
     - `routers/llm.py`: AI chat execution and model selector endpoints.
   - Extracted 50+ lines of inline Schwab success HTML to `backend/templates/schwab_success.html`.
   - Migrated from deprecated `@app.on_event("startup")` to the modern FastAPI `lifespan` context manager.

3. **Centralized Constants & Date Safety**:
   - Created `backend/constants.py` for `DEFAULT_TICKERS`, `DEFAULT_ACCOUNT_ID`, `INITIAL_CASH_BALANCE`, and `DEFAULT_USER_ID`.
   - Replaced deprecated `datetime.utcnow()` calls with Python 3.12+ `datetime.now(timezone.utc)` across all modules.

4. **Frontend Architecture & Type Safety**:
   - Created `frontend/src/types/index.ts` defining typed domain interfaces (`Portfolio`, `Position`, `Trade`, `WatchlistItem`, `ChatMessage`, `AuthStatus`).
   - Created `frontend/src/lib/api.ts` centralized fetch client.
   - Created `frontend/src/contexts/AuthContext.tsx` to share auth state globally across components (eliminating 4 duplicate network fetches).
   - Created `frontend/src/hooks/useWorkstationRefresh.ts` to centralize `refresh-workstation` event handling.
   - Removed dead auth-gate code from `Dashboard.tsx`.
   - Fixed `useCallback` dependency array bug in `ModelSelector.tsx`.
   - Removed `ignoreBuildErrors: true` from `next.config.mjs` — verified clean build with strict TypeScript type checking.

5. **CI/CD Workflow**:
   - Added `.github/workflows/ci.yml` running backend tests (`pytest`), frontend type checking (`tsc --noEmit`), and Next.js static build on pushes and PRs.

---

### Automated Verification

- **Backend Pytest Suite**: 13/13 tests passing cleanly (`uv run pytest` in `backend/`).
- **Frontend Type Check & Build**: Next.js 14 static export succeeded with 0 errors (`npm run build`).
- **Regression Test Ledger**: Updated [REGRESSION_TESTS.md](file:///c:/Users/ullul/PycharmProjects/finagy/planning/REGRESSION_TESTS.md#L76).
