# Repository Coding Directives & Standards

This document establishes the mandatory development standards and quality directives for all AI agent and human contributions in the **FinAlly** repository.

---

## 1. Dead Code & AI Slop Prohibition
- **No Diagnostic Print Statements:** Never commit unstructured `print()` debug logs. Use Python's standard `logging` module (`logger = logging.getLogger(__name__)`) in the backend, or structured console logging in the frontend.
- **No Commented-Out Code:** Remove obsolete, commented-out code snippets, alternative implementations, and unused function prototypes.
- **Clean Imports:** Keep imports organized and free of unused dependencies or dead module imports.
- **Scratch Files:** Do not leave temporary test or scratch scripts (`test_*.py`, `scratch_*.js`) in the root directory. Store one-off test utilities in designated test suites (`backend/tests/`) or artifact directories.

---

## 2. Type System & Schema Validation
- **Backend (Python / FastAPI):**
  - All router endpoints, helper functions, and service methods MUST specify explicit parameter and return type annotations.
  - Request and response payloads MUST use explicit Pydantic models (`pydantic.BaseModel`).
- **Frontend (TypeScript / React):**
  - Strict TypeScript mode MUST be respected. Avoid `any` types; use explicit interfaces or type aliases (`src/types/index.ts`).
  - React component props MUST be explicitly typed.

---

## 3. Error Handling & Exception Propagation
- **FastAPI Handlers:** Raise standard `fastapi.HTTPException` with appropriate status codes (`400`, `401`, `403`, `404`, `500`) and structured detail messages.
- **No Silent Exception Swallowing:** Never use empty `except Exception: pass` or return `None` without logging the failure root cause.
- **Resilient Fallbacks:** Fallback mocks (e.g. for offline market data or disconnected LLM API) must be explicit, documented, and restricted to offline/mock modes.

---

## 4. Security & Environment Sanity
- **No Hardcoded Secrets:** API keys, database URLs, Twilio tokens, and Schwab secrets must strictly be loaded from environment variables (`.env`).
- **Cryptographic Verification:** Webhook endpoints (e.g. Twilio) must cryptographically validate request signatures in production environments.

---

## 5. Automated Verification Gate
- Every feature or refactoring branch MUST pass the following automated quality checks before merging:
  - Backend: `uv run pytest` (100% pass rate on unit test suite).
  - Backend Linter: `uv run ruff check`
  - Frontend: `npm run lint` & `npm run build`

---

## 6. Development Slash Commands
- **`/ship [optional comment]`**: Stages all modified files (`git add .`), commits with a Conventional Commit message (or user-supplied comment), pushes the current branch to `origin`, and opens a structured GitHub Pull Request.
- **`/land`**: Completes post-merge cleanup by checking out `main`, pulling latest changes, deleting merged local and remote feature branches, pruning tracking references (`git fetch --prune`), and running test suite verification.
- **`/goal`**: Triggers autonomous, extra-thorough execution mode for complex multi-file refactoring or long-running tasks.
- **`/schedule`**: Schedules background cron jobs or one-shot timers for background notifications and evaluations.
- **`/grill-me`**: Initiates an interactive interview session to align on design decisions and resolve architecture trade-offs.
- **`/learn`**: Teaches the agent new repository patterns or corrects past behaviors, persisting them for future sessions.
- **`/sandbox [branch-name]`**: Emulates Claude Code sandbox mode with isolated branch execution, autonomous reads/network access, and paid API cost guardrails.

---

## 7. Usage Allocation & Efficiency Guidelines
- **Externalize Builds & Tests:** To conserve the user's weekly usage quota, agents should prioritize asking the user to run intensive commands (like `npm run build`, `npm run lint`, or `uv run pytest`) manually in their local workstation terminal and report the final outcome/logs back, rather than running them directly inside the agent's execution context.

