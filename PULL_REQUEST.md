# Pull Request Template & Description

## Summary of Changes
Provide a clear description of the problem, feature, or refactoring delivered in this Pull Request.

---

### Key Highlights & Technical Changes
- List specific architectural modifications, new endpoints, or UI components.
- Highlight key design decisions or non-obvious rationale.

---

## 🧹 Code Hygiene & Quality Checklist
Before requesting review or merging, verify all items:
- [ ] **No AI Slop / Debug Logs:** Removed all diagnostic `print()` statements, temporary logs, and commented-out code.
- [ ] **Type Annotations:** All Python functions have explicit type hints; all TypeScript components/props have explicit types (zero `any`).
- [ ] **Error Handling:** Exceptions are caught cleanly and raised as structured `fastapi.HTTPException` with proper status codes. No empty `except Exception: pass` blocks.
- [ ] **Secrets & Config:** Confirmed no API keys, tokens, or credentials are hardcoded.
- [ ] **Clean Imports:** Removed unused imports and scratch test scripts from root.

---

## 🧪 Automated Verification
- [ ] **Backend Unit Tests:** `uv run pytest` (100% pass rate).
- [ ] **Backend Linter:** `uv run ruff check` (or clean static analysis).
- [ ] **Frontend Build & Types:** `npm run build` (0 type errors, clean static export).
