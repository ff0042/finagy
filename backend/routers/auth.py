
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
import os

from backend.constants import DEFAULT_ACCOUNT_ID, DEFAULT_USER_ID, INITIAL_CASH_BALANCE
from backend.db.database import (
    execute_query,
    reset_session_state,
    set_active_account,
)
from backend.schwab_service import schwab_service

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/schwab/auth-status")
def auth_status():
    return schwab_service.get_token_status()

@router.get("/api/schwab/token")
def get_access_token():
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env in ("production", "prod"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    status_info = schwab_service.get_token_status()
    if status_info.get("authenticated") and schwab_service.client and schwab_service.client.tokens:
        return {"access_token": schwab_service.client.tokens.access_token}
    return {"access_token": None, "error": "Not authenticated"}

@router.get("/api/schwab/auth-url")
def schwab_login():
    url = schwab_service.get_auth_url()
    return {"auth_url": url}

@router.get("/api/schwab/callback")
def schwab_callback(request: Request):
    code = request.query_params.get("code")
    session_id = request.query_params.get("session")
    error = request.query_params.get("error")
    
    if error:
        return _render_html(False, error)
        
    if not code:
        return _render_html(False, "No auth code provided by Schwab")
        
    res = schwab_service.exchange_code_for_tokens(code)
    
    if res.get("success"):
        try:
            accounts = schwab_service.get_linked_accounts()
            now = datetime.now(UTC).isoformat()
            for i, acc in enumerate(accounts):
                acc_hash = acc.get("account_hash")
                acc_num = acc.get("account_number")
                acct_id = acc.get("id")
                name = acc.get("name")
                cash_bal = acc.get("cash_balance", INITIAL_CASH_BALANCE)
                
                if not acc_hash:
                    continue
                    
                rows = execute_query("SELECT id FROM accounts WHERE account_hash = ?", (acc_hash,))
                if rows:
                    execute_query("UPDATE accounts SET is_active = ? WHERE account_hash = ?", (1 if i == 0 else 0, acc_hash))
                else:
                    execute_query(
                        "INSERT INTO accounts (id, user_id, account_number, account_hash, name, type, is_active, cash_balance, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (acct_id, DEFAULT_USER_ID, acc_num, acc_hash, name, "SCHWAB", 1 if i == 0 else 0, cash_bal, now)
                    )
                    from backend.constants import DEFAULT_TICKERS
                    import uuid
                    for ticker in DEFAULT_TICKERS:
                        try:
                            execute_query(
                                "INSERT INTO watchlist (id, user_id, account_id, ticker, added_at) VALUES (?, ?, ?, ?, ?)",
                                (str(uuid.uuid4()), DEFAULT_USER_ID, acct_id, ticker, now)
                            )
                        except Exception:
                            pass
                if i == 0:
                    set_active_account(rows[0]["id"] if rows else acct_id)
        except Exception as e:
            logger.error(f"Failed to sync Schwab accounts: {e}")
            
    return _render_html(res.get("success", False), res.get("error", ""))

@router.post("/api/schwab/disconnect")
def disconnect_schwab():
    schwab_service.disconnect()
    execute_query("UPDATE accounts SET is_active = 0 WHERE type = 'SCHWAB'")
    execute_query("UPDATE accounts SET is_active = 1 WHERE id = ?", (DEFAULT_ACCOUNT_ID,))
    return {"status": "ok"}

@router.post("/api/session/reset")
def reset_session():
    reset_session_state()
    return {"status": "ok"}

from pathlib import Path


def _render_html(success, error_msg):
    template_path = Path(__file__).resolve().parent.parent / "templates" / "schwab_success.html"
    if template_path.exists():
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template = f.read()
                return HTMLResponse(content=template)
        except Exception as e:
            logger.error(f"Failed to read schwab_success.html: {e}")
            
    # Self-contained fallback HTML that notifies opener and closes popup automatically
    script = """
    <script>
        if (window.opener) {
            try { window.opener.postMessage("schwab-auth-success", "*"); } catch(e) {}
        }
        setTimeout(function() { window.close(); }, 800);
    </script>
    """
    if success:
        content = f"<html><body style='background:#0d1117;color:#fff;font-family:sans-serif;text-align:center;padding-top:20%;'><h2>Schwab Connected!</h2><p>Closing window...</p>{script}</body></html>"
    else:
        content = f"<html><body style='background:#0d1117;color:#fff;font-family:sans-serif;text-align:center;padding-top:20%;'><h2 style='color:#f85149;'>Connection Failed</h2><p>{error_msg}</p>{script}</body></html>"
    return HTMLResponse(content=content)
