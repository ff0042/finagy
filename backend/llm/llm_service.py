from backend.trade_service import execute_actions
import json
import os
import re
import uuid
from datetime import datetime, timezone
from openai import OpenAI
from backend.db.database import execute_query, get_active_account

SYSTEM_PROMPT = """You are FinAlly, an AI trading workstation assistant.
You analyze portfolio positions, cash balance, and watchlist prices to execute user requests.

CRITICAL INSTRUCTIONS:
1. When the user asks to buy or sell stock (e.g., "buy 10 shares of AAPL", "sell 2 shares of GOOGL"), populate the "trades" array:
   {"ticker": "AAPL", "side": "buy", "quantity": 10}
   Do NOT place buy/sell trade orders into "watchlist_changes".
2. When the user asks to add or remove a ticker from their watchlist (e.g., "add IBIT to watchlist", "remove TSLA from watchlist"), populate "watchlist_changes":
   {"ticker": "IBIT", "action": "add"}
3. If the user asks for analysis or general advice, answer concisely in "message" and leave "trades" and "watchlist_changes" as empty arrays [].

Always return valid JSON matching this schema:
{
  "message": "Conversational reply summarizing your action or analysis",
  "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
  "watchlist_changes": [{"ticker": "IBIT", "action": "add"}]
}
"""

def generate_mock_response(user_message: str):
    msg_lower = user_message.lower().strip()
    
    trades = []
    watchlist_changes = []

    fallback_msg = "I don't know how to do that with the Free Deterministic Engine. Consider using a smarter model (e.g. Gemini 2.5 Flash or DeepSeek R1) in the header model selector."

    if any(phrase in msg_lower for phrase in ["sell all", "dump all", "close all", "all positions", "everything"]):
        return {"message": fallback_msg, "trades": [], "watchlist_changes": []}

    # Mechanical Buy / Purchase / Order
    buy_match = re.search(r'\b(?:buy|purchase|order)\s+(\d+)?\s*(?:shares?\s+of\s+)?([a-z]{1,5})\b', msg_lower)
    # Mechanical Sell
    sell_match = re.search(r'\b(?:sell|dump)\s+(\d+)?\s*(?:shares?\s+of\s+)?([a-z]{1,5})\b', msg_lower)
    # Add to Watchlist
    add_wl_match = re.search(r'\b(?:add|watch|track)\s+([a-z]{1,5})(?:\s+to\s+(?:the\s+)?watchlist)?\b', msg_lower)
    # Remove from Watchlist
    rem_wl_match = re.search(r'\b(?:remove|unwatch|delete)\s+([a-z]{1,5})(?:\s+from\s+(?:the\s+)?watchlist)?\b', msg_lower)
    # Portfolio / Cash Query
    status_match = re.search(r'\b(?:portfolio|cash|balance|positions|status|hello|hi|help)\b', msg_lower)

    if buy_match:
        ticker = buy_match.group(2).upper()
        if ticker in ["ALL", "EVERYTHING", "THE", "MY", "POSITIONS"]:
            return {"message": fallback_msg, "trades": [], "watchlist_changes": []}
        qty = int(buy_match.group(1)) if buy_match.group(1) else 1
        trades.append({"ticker": ticker, "side": "buy", "quantity": qty})
        response_text = f"Executed purchase of {qty} share(s) of {ticker} at market price."

    elif sell_match:
        ticker = sell_match.group(2).upper()
        if ticker in ["ALL", "EVERYTHING", "POSITIONS", "PORTFOLIO", "THE", "MY"]:
            return {"message": fallback_msg, "trades": [], "watchlist_changes": []}
        
        # Check active account positions to prevent short sales in deterministic engine
        active = get_active_account()
        acct_id = active["id"] if active else "acct_roth"
        owned_rows = execute_query(
            "SELECT quantity FROM positions WHERE user_id = 'default' AND account_id = ? AND UPPER(ticker) = ?",
            (acct_id, ticker)
        )
        owned_qty = sum(r["quantity"] for r in owned_rows) if owned_rows else 0.0
        
        if owned_qty <= 0:
            return {"message": fallback_msg, "trades": [], "watchlist_changes": []}

        requested_qty = int(sell_match.group(1)) if sell_match.group(1) else int(owned_qty)
        qty = min(requested_qty, int(owned_qty))
        
        trades.append({"ticker": ticker, "side": "sell", "quantity": qty})
        response_text = f"Executed sale of {qty} share(s) of {ticker} at market price."

    elif add_wl_match:
        ticker = add_wl_match.group(1).upper()
        if ticker in ["ALL", "THE", "MY"]:
            return {"message": fallback_msg, "trades": [], "watchlist_changes": []}
        watchlist_changes.append({"ticker": ticker, "action": "add"})
        response_text = f"{ticker} has been added to your watchlist."

    elif rem_wl_match:
        ticker = rem_wl_match.group(1).upper()
        if ticker in ["ALL", "THE", "MY"]:
            return {"message": fallback_msg, "trades": [], "watchlist_changes": []}
        watchlist_changes.append({"ticker": ticker, "action": "remove"})
        response_text = f"{ticker} has been removed from your watchlist."

    elif status_match:
        response_text = "Workstation active. You can execute mechanical trade commands (e.g. 'buy 10 AAPL', 'add IBIT to watchlist') or switch to a smarter AI model for strategy advice."

    else:
        response_text = fallback_msg

    return {
        "message": response_text,
        "trades": trades,
        "watchlist_changes": watchlist_changes
    }

AVAILABLE_MODELS = [
    {
        "id": "mock/deterministic",
        "name": "Deterministic Engine (Free)",
        "cost_tier": "FREE",
        "best_for": "Zero-cost basic mechanical trades & watchlist commands"
    },
    {
        "id": "google/gemini-2.5-flash-lite",
        "name": "Gemini 2.5 Flash Lite",
        "cost_tier": "$",
        "best_for": "High-volume simple trade & watchlist commands"
    },
    {
        "id": "google/gemini-2.5-flash",
        "name": "Gemini 2.5 Flash",
        "cost_tier": "$$",
        "best_for": "Best overall value for mechanical trades & chat"
    },
    {
        "id": "deepseek/deepseek-r1",
        "name": "DeepSeek R1",
        "cost_tier": "$$$",
        "best_for": "Options strategies (iron condors), Sharpe ratio & risk math"
    },
    {
        "id": "google/gemini-3.1-pro-preview",
        "name": "Gemini 3.1 Pro Preview",
        "cost_tier": "$$$$",
        "best_for": "Long context macro synthesis & complex portfolio strategy"
    },
    {
        "id": "anthropic/claude-3.7-sonnet",
        "name": "Claude 3.7 Sonnet",
        "cost_tier": "$$$$$",
        "best_for": "Executive financial reports & detailed written analysis"
    }
]

_active_model = None

def get_active_model() -> str:
    global _active_model
    if _active_model:
        return _active_model
        
    env_model = os.getenv("OPENROUTER_MODEL") or os.getenv("LLM_MODEL")
    if env_model:
        return env_model

    try:
        from backend.schwab_service import schwab_service
        is_authed = schwab_service.get_token_status().get("authenticated", False)
    except Exception:
        is_authed = False

    if not is_authed:
        return "mock/deterministic"
        
    return "mock/deterministic"

def set_active_model(model_id: str) -> str:
    global _active_model
    if model_id:
        _active_model = model_id
    return get_active_model()

def process_chat(user_message: str, portfolio_context: dict, chat_history: list):
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    is_placeholder_key = not api_key or "your-key-here" in api_key.lower() or "your-openrouter-key" in api_key.lower()
    
    model_name = get_active_model()
    is_mock = os.getenv("LLM_MOCK", "false").lower() == "true" or is_placeholder_key or model_name == "mock/deterministic"

    if is_mock:
        response_data = generate_mock_response(user_message)
    else:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.append({
            "role": "system",
            "content": f"Current Context:\n{json.dumps(portfolio_context)}"
        })
        for msg in chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        try:
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key
            )
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            response_data = json.loads(content)
        except Exception as e:
            print(f"[WARN] LLM API error: {e}")
            response_data = generate_mock_response(user_message)

    execute_actions(response_data)
    
    execute_query(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), "default", "user", user_message, None, datetime.now(timezone.utc).isoformat())
    )
    execute_query(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), "default", "assistant", response_data.get("message", ""), json.dumps({
            "trades": response_data.get("trades", []),
            "watchlist_changes": response_data.get("watchlist_changes", [])
        }), datetime.now(timezone.utc).isoformat())
    )
    
    return response_data

