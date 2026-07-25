import json
import os
import re
import uuid
from datetime import datetime
from openai import OpenAI
from db.database import execute_query

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
    response_text = ""

    # Check for buy command: e.g. "buy 10 shares of AAPL", "please buy 1 AAPL", "buy AAPL"
    buy_match = re.search(r'\bbuy\s+(\d+)?\s*(?:shares?\s+of\s+)?([a-z]{1,5})\b', msg_lower)
    # Check for sell command: e.g. "sell 5 shares of AAPL", "sell AAPL"
    sell_match = re.search(r'\bsell\s+(\d+)?\s*(?:shares?\s+of\s+)?([a-z]{1,5})\b', msg_lower)
    # Check for watchlist add command: e.g. "add ibit to watchlist", "please add ibit to watchlist", "watch ibit"
    add_wl_match = re.search(r'\b(?:add|watch)\s+([a-z]{1,5})(?:\s+to\s+(?:the\s+)?watchlist)?\b', msg_lower)
    # Check for watchlist remove command: e.g. "remove ibit from watchlist"
    rem_wl_match = re.search(r'\bremove\s+([a-z]{1,5})\s+from\s+(?:the\s+)?watchlist\b', msg_lower)

    if buy_match:
        qty = int(buy_match.group(1)) if buy_match.group(1) else 1
        ticker = buy_match.group(2).upper()
        trades.append({"ticker": ticker, "side": "buy", "quantity": qty})
        response_text = f"Executed purchase of {qty} share(s) of {ticker} at market price."
    elif sell_match:
        qty = int(sell_match.group(1)) if sell_match.group(1) else 1
        ticker = sell_match.group(2).upper()
        trades.append({"ticker": ticker, "side": "sell", "quantity": qty})
        response_text = f"Executed sale of {qty} share(s) of {ticker} at market price."
    elif add_wl_match:
        ticker = add_wl_match.group(1).upper()
        watchlist_changes.append({"ticker": ticker, "action": "add"})
        response_text = f"{ticker} has been added to your watchlist."
    elif rem_wl_match:
        ticker = rem_wl_match.group(1).upper()
        watchlist_changes.append({"ticker": ticker, "action": "remove"})
        response_text = f"{ticker} has been removed from your watchlist."
    else:
        response_text = f"Analyzed request: '{user_message}'. Portfolio is active."

    return {
        "message": response_text,
        "trades": trades,
        "watchlist_changes": watchlist_changes
    }

def process_chat(user_message: str, portfolio_context: dict, chat_history: list):
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    is_mock = os.getenv("LLM_MOCK", "false").lower() == "true" or not api_key

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
                model=os.getenv("LLM_MODEL", "openrouter/openai/gpt-4o"),
                messages=messages,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            response_data = json.loads(content)
        except Exception as e:
            # Fallback to intelligent pattern parsing if LLM call fails
            response_data = generate_mock_response(user_message)
            response_data["message"] = f"Error calling LLM ({str(e)}). Fallback executed: {response_data['message']}"

    # Execute trades and watchlist actions immediately
    execute_actions(response_data)
    
    # Persist conversation
    execute_query(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), "default", "user", user_message, None, datetime.utcnow().isoformat())
    )
    execute_query(
        "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), "default", "assistant", response_data.get("message", ""), json.dumps({
            "trades": response_data.get("trades", []),
            "watchlist_changes": response_data.get("watchlist_changes", [])
        }), datetime.utcnow().isoformat())
    )
    
    return response_data

def execute_actions(response_data):
    trades = response_data.get("trades", [])
    watchlist_changes = response_data.get("watchlist_changes", [])
    
    from market_data import get_market_data_provider, price_cache
    market_provider = get_market_data_provider()
    
    for w in watchlist_changes:
        ticker = w.get("ticker", "").upper()
        action = w.get("action", "").lower()
        if not ticker:
            continue
        if action == "add":
            try:
                execute_query(
                    "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), "default", ticker, datetime.utcnow().isoformat())
                )
            except Exception:
                pass
            market_provider.add_ticker(ticker)
        elif action == "remove":
            execute_query(
                "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
                ("default", ticker)
            )
            
    for t in trades:
        ticker = t.get("ticker", "").upper()
        side = t.get("side", "").lower()
        quantity = float(t.get("quantity", 0))
        
        if quantity <= 0 or not ticker:
            continue
            
        market_provider.add_ticker(ticker)
        current_price = price_cache.get(ticker)
        price = current_price["price"] if current_price else 150.0
        total_cost = price * quantity
        
        user_rows = execute_query("SELECT cash_balance FROM users_profile WHERE id = 'default'")
        if not user_rows:
            continue
        cash = user_rows[0]["cash_balance"]
        
        position = execute_query("SELECT quantity, avg_cost FROM positions WHERE user_id = 'default' AND ticker = ?", (ticker,))
        pos_qty = position[0]["quantity"] if position else 0
        avg_cost = position[0]["avg_cost"] if position else 0
        
        if side == "buy":
            if cash < total_cost:
                continue # Insufficient funds
            
            new_cash = cash - total_cost
            new_qty = pos_qty + quantity
            new_avg = ((pos_qty * avg_cost) + total_cost) / new_qty if new_qty > 0 else 0
            
            execute_query("UPDATE users_profile SET cash_balance = ? WHERE id = 'default'", (new_cash,))
            if position:
                execute_query("UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? WHERE user_id = 'default' AND ticker = ?",
                              (new_qty, new_avg, datetime.utcnow().isoformat(), ticker))
            else:
                execute_query("INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                              (str(uuid.uuid4()), "default", ticker, new_qty, new_avg, datetime.utcnow().isoformat()))
                              
            execute_query("INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (str(uuid.uuid4()), "default", ticker, side, quantity, price, datetime.utcnow().isoformat()))
                          
        elif side == "sell":
            if pos_qty < quantity:
                continue # Insufficient shares
                
            new_cash = cash + total_cost
            new_qty = pos_qty - quantity
            
            execute_query("UPDATE users_profile SET cash_balance = ? WHERE id = 'default'", (new_cash,))
            if new_qty > 0:
                execute_query("UPDATE positions SET quantity = ?, updated_at = ? WHERE user_id = 'default' AND ticker = ?",
                              (new_qty, datetime.utcnow().isoformat(), ticker))
            else:
                execute_query("DELETE FROM positions WHERE user_id = 'default' AND ticker = ?", (ticker,))
                
            execute_query("INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (str(uuid.uuid4()), "default", ticker, side, quantity, price, datetime.utcnow().isoformat()))
