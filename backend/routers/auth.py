
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
import os
import json
from datetime import datetime, timezone
from backend.db.database import execute_query, get_active_account, set_active_account, reset_session_state
from backend.schwab_service import schwab_service
from backend.constants import DEFAULT_USER_ID, DEFAULT_ACCOUNT_ID, INITIAL_CASH_BALANCE
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/schwab/auth-status")
def auth_status():
    return schwab_service.get_token_status()

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
        
    res = schwab_service.exchange_code_for_token(code)
    
    if res.get("success"):
        try:
            acct_res = schwab_service.get_account_numbers()
            if acct_res.get("success") and acct_res.get("data"):
                accounts = acct_res["data"]
                now = datetime.now(timezone.utc).isoformat()
                for i, acc in enumerate(accounts):
                    acc_hash = acc.get("hashValue")
                    acc_num = acc.get("accountNumber")
                    
                    if not acc_hash:
                        continue
                        
                    acct_id = f"schwab_{acc_hash[:8]}"
                    
                    rows = execute_query("SELECT id FROM accounts WHERE account_hash = ?", (acc_hash,))
                    if rows:
                        execute_query("UPDATE accounts SET is_active = ? WHERE account_hash = ?", (1 if i == 0 else 0, acc_hash))
                    else:
                        execute_query(
                            "INSERT INTO accounts (id, user_id, account_number, account_hash, name, type, is_active, cash_balance, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (acct_id, DEFAULT_USER_ID, acc_num, acc_hash, f"Schwab - {acc_num[-4:]}", "SCHWAB", 1 if i == 0 else 0, INITIAL_CASH_BALANCE, now)
                        )
                    if i == 0:
                        set_active_account(rows[0]["id"] if rows else acct_id)
        except Exception as e:
            logger.error(f"Failed to sync Schwab accounts: {e}")
            
    return _render_html(res.get("success", False), res.get("error", ""))

@router.post("/api/schwab/disconnect")
def disconnect_schwab():
    schwab_service.disconnect()
    execute_query("DELETE FROM accounts WHERE type = 'SCHWAB'")
    reset_session_state()
    return {"status": "ok"}

@router.post("/api/session/reset")
def reset_session():
    reset_session_state()
    return {"status": "ok"}

def _render_html(success, error_msg):
    try:
        with open("backend/templates/schwab_success.html", "r") as f:
            template = f.read()
            return HTMLResponse(content=template)
    except Exception:
        # Fallback simple HTML
        return HTMLResponse(content=f"<html><body>{'Success' if success else 'Error: ' + error_msg}</body></html>")
