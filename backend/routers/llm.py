from fastapi import APIRouter
from pydantic import BaseModel

from backend.constants import DEFAULT_USER_ID
from backend.db.database import execute_query
from backend.llm.llm_service import get_active_model, process_chat, set_active_model
from backend.routers.portfolio import get_portfolio
from backend.routers.watchlist import get_watchlist
from backend.routers.orders import get_orders

router = APIRouter()

class ChatRequest(BaseModel):
    message: str



@router.post("/api/chat")
def chat(req: ChatRequest):
    portfolio = get_portfolio()
    wl = get_watchlist()
    orders = get_orders()
    context = {
        "portfolio": portfolio,
        "watchlist": wl,
        "open_orders": orders
    }

    
    history_rows = execute_query("SELECT role, content FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (DEFAULT_USER_ID,))
    history = [{"role": r["role"], "content": r["content"]} for r in reversed(history_rows)]
    
    res = process_chat(req.message, context, history)
    return res

@router.get("/api/chat/history")
def get_chat_history():
    rows = execute_query("SELECT role, content FROM chat_messages WHERE user_id = ? ORDER BY created_at ASC", (DEFAULT_USER_ID,))
    return [{"role": r["role"], "content": r["content"]} for r in rows]

from backend.llm.llm_service import AVAILABLE_MODELS


class ModelSelectRequest(BaseModel):
    model: str

@router.get("/api/llm/models")
@router.get("/api/models/active")
def get_models():
    return {"active_model": get_active_model(), "models": AVAILABLE_MODELS}

@router.post("/api/llm/model")
@router.post("/api/models/select")
def select_model(req: ModelSelectRequest):
    updated = set_active_model(req.model)
    return {"status": "ok", "active_model": updated}

from backend.llm.llm_service import get_autonomous_mode, set_autonomous_mode


class AutonomySelectRequest(BaseModel):
    enabled: bool

@router.get("/api/llm/autonomy")
def get_autonomy():
    return {"enabled": get_autonomous_mode()}

@router.post("/api/llm/autonomy")
def set_autonomy(req: AutonomySelectRequest):
    updated = set_autonomous_mode(req.enabled)
    return {"status": "ok", "enabled": updated}

import logging
import os

from fastapi import Form, HTTPException, Request

from backend.scheduler import execute_background_task

try:
    from twilio.request_validator import RequestValidator
except ImportError:
    RequestValidator = None

@router.post("/api/twilio/webhook")
async def twilio_webhook(request: Request, Body: str = Form(...), From: str = Form(...)):
    # 1. Caller ID Check
    allowed_number = os.getenv("USER_PHONE_NUMBER", "").strip()
    if not allowed_number or From != allowed_number:
        logging.warning(f"[SECURITY ALERT] Rejected unauthorized SMS from {From}")
        raise HTTPException(status_code=403, detail="Unauthorized sender")

    # 2. Cryptographic Signature Check
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if auth_token and auth_token != "your_twilio_auth_token_here":
        if RequestValidator is None:
            raise HTTPException(status_code=500, detail="Twilio package not installed")
        validator = RequestValidator(auth_token)
        signature = request.headers.get("X-Twilio-Signature", "")
        url = str(request.url).replace("http://", "https://") if request.headers.get("x-forwarded-proto") == "https" else str(request.url)
        form_data = await request.form()
        post_vars = {k: v for k, v in form_data.items()}
        
        if not validator.validate(url, post_vars, signature):
            logging.warning("[SECURITY ALERT] Invalid Twilio Signature detected!")
            raise HTTPException(status_code=403, detail="Invalid Twilio Signature")

    logging.info(f"[TWILIO WEBHOOK] Received text from {From}: {Body}")
    # Trigger background evaluation with user's text as the prompt
    execute_background_task(f"User replied via SMS: {Body}")
    return {"status": "ok"}
