# Periodic Code Health Check & Maintenance Protocol

This document defines the recurring protocol and execution prompt for conducting periodic code reviews, technical debt audits, AI slop removal, and architectural maintenance across the **FinAlly** repository.

---

## 1. Execution Prompt for AI Assistant / Developer

Copy and execute the following prompt periodically (e.g. bi-weekly or before major release milestones):

```markdown
/goal Perform a Periodic Code Health Check & Technical Debt Audit on the FinAlly codebase.

### Scope of Maintenance Check:

1. **Dead Code & AI Slop Sweeping:**
   - Scan both `backend/` and `frontend/` for orphaned variables, unused functions, dead module imports, and temporary debug scripts.
   - Detect and remove diagnostic `print()` or `console.log()` calls that slipped into production code paths.
   - Search for obsolete commented-out blocks of code and remove them.

2. **Error Handling & Exception Transparency:**
   - Audit `backend/routers/` to ensure all API errors use structured `fastapi.HTTPException` with proper status codes.
   - Verify zero empty `except Exception: pass` blocks exist across Python modules.

3. **Type Annotation & Schema Strictness:**
   - Verify Python type annotations in `backend/` (all function parameters and return types specified).
   - Verify TypeScript strictness in `frontend/src/` (zero `any` types, explicit React prop interface declarations).

4. **Security & Configuration Sanity:**
   - Check that no API keys, tokens, or environment-specific credentials are hardcoded.
   - Ensure default fallback values are safe for production environments.

5. **Dependency & Test Suite Health:**
   - Run `uv run pytest` in `backend/` and verify 100% pass rate.
   - Run `npm run build` and `npm run lint` in `frontend/` to confirm clean builds.

### Output Required:
Provide a structured summary report detailing:
- Files audited and specific cleanups applied.
- Code smells, slop, or anti-patterns eliminated.
- Test verification and build status.
```

---

## 2. Recommended Cadence & Workflow Integration
- **Bi-Weekly / Sprint End:** Run this health check prompt at the end of each development sprint before cutting release tags.
- **Pre-Merge Audit:** Run the prompt on major refactoring or feature branches before opening Pull Requests.
- **Continuous Enforcement:** Ensure `.agents/AGENTS.md` and `PULL_REQUEST.md` checklists are enforced during everyday development.
