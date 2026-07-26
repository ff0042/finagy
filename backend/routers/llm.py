
from fastapi import APIRouter
from pydantic import BaseModel
from backend.llm.llm_service import process_chat, get_active_model, set_active_model
from backend.routers.portfolio import get_portfolio
from backend.routers.watchlist import get_watchlist
from backend.db.database import execute_query
from backend.constants import DEFAULT_USER_ID

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

@router.post("/api/chat")
def chat(req: ChatRequest):
    portfolio = get_portfolio()
    wl = get_watchlist()
    context = {
        "portfolio": portfolio,
        "watchlist": wl
    }
    
    history_rows = execute_query("SELECT role, content FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (DEFAULT_USER_ID,))
    history = [{"role": r["role"], "content": r["content"]} for r in reversed(history_rows)]
    
    res = process_chat(req.message, context, history)
    return res

@router.get("/api/chat/history")
def get_chat_history():
    rows = execute_query("SELECT role, content FROM chat_messages WHERE user_id = ? ORDER BY created_at ASC", (DEFAULT_USER_ID,))
    return [{"role": r["role"], "content": r["content"]} for r in rows]

from backend.llm.llm_service import process_chat, get_active_model, set_active_model, AVAILABLE_MODELS

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
