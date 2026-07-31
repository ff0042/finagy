import logging
import uuid
from datetime import UTC, datetime

from backend.constants import DEFAULT_ACCOUNT_ID, DEFAULT_USER_ID
from backend.db.database import execute_query, get_active_account, get_connection
from backend.market_data import (
    fetch_real_market_price,
    get_market_data_provider,
    price_cache,
)
from backend.schwab_service import schwab_service

logger = logging.getLogger(__name__)

def execute_actions(response_data, account_id=None):
    watchlist_changes = response_data.get("watchlist_changes", [])
    
    market_provider = get_market_data_provider()
    
    schwab_connected = schwab_service.get_token_status().get("authenticated", False)

    if not account_id:
        active_acct = get_active_account()
        acct_id = active_acct["id"] if active_acct else DEFAULT_ACCOUNT_ID
        acct_type = active_acct["type"] if active_acct else "LOCAL"
        acct_hash = active_acct.get("account_hash") if active_acct else None
    else:
        acct_id = account_id
        if schwab_connected and acct_id.startswith("schwab_"):
            acct_type = "SCHWAB"
            accounts = schwab_service.get_linked_accounts()
            acct_hash = next((a["account_hash"] for a in accounts if a["id"] == acct_id), None)
        else:
            rows = execute_query("SELECT type, account_hash FROM accounts WHERE id = ?", (acct_id,))
            acct_type = rows[0]["type"] if rows else "LOCAL"
            acct_hash = rows[0]["account_hash"] if rows else None

    executed_watchlist = []
    failed_watchlist = []
    executed_orders = []
    failed_orders = []

    # Process Watchlist (Always local - skip in Schwab mode)
    if not (schwab_connected and acct_type == "SCHWAB"):
        for w in watchlist_changes:
            ticker = w.get("ticker", "").upper()
            action = w.get("action", "").lower()
            if not ticker:
                continue
            if action == "add":
                existing = execute_query(
                    "SELECT id FROM watchlist WHERE user_id = ? AND account_id = ? AND UPPER(ticker) = ?",
                    (DEFAULT_USER_ID, acct_id, ticker)
                )
                if existing:
                    executed_watchlist.append(ticker)
                else:
                    try:
                        execute_query(
                            "INSERT INTO watchlist (id, user_id, account_id, ticker, added_at) VALUES (?, ?, ?, ?, ?)",
                            (str(uuid.uuid4()), DEFAULT_USER_ID, acct_id, ticker, datetime.now(UTC).isoformat())
                        )
                        executed_watchlist.append(ticker)
                    except Exception as e:
                        logger.warning(f"Failed to add {ticker} to watchlist: {e}")
                        failed_watchlist.append(ticker)
                market_provider.add_ticker(ticker)
            elif action == "remove":
                try:
                    execute_query(
                        "DELETE FROM watchlist WHERE user_id = ? AND account_id = ? AND UPPER(ticker) = ?",
                        (DEFAULT_USER_ID, acct_id, ticker)
                    )
                    executed_watchlist.append(ticker)
                except Exception:
                    failed_watchlist.append(ticker)
            
    is_schwab = (acct_type == "SCHWAB") and schwab_connected and acct_hash

    # Process Orders/Trades
    orders = response_data.get("orders", [])
    
    # Backwards compatibility with previous "trades" key
    if not orders and "trades" in response_data:
        for t in response_data["trades"]:
            t["action"] = "submit"
            t["order_type"] = "market"
            orders.append(t)

    for o in orders:
        action = o.get("action", "submit").lower()
        
        if action == "cancel":
            order_id = o.get("order_id")
            if not order_id: continue
            if is_schwab:
                res = schwab_service.cancel_order(acct_hash, order_id)
                if not res.get("success"):
                    logger.error(f"Schwab cancel order failed: {res}")
            else:
                # Cancel local order
                execute_query("UPDATE orders SET status = 'CANCELED', updated_at = ? WHERE id = ?", 
                              (datetime.now(UTC).isoformat(), order_id))
            continue
            
        # Submit new order
        ticker = o.get("ticker", "").upper()
        side = o.get("side", "").lower()
        quantity = float(o.get("quantity", 0))
        order_type = o.get("order_type", "market").lower()
        limit_price = o.get("limit_price")
        stop_price = o.get("stop_price")
        tif = o.get("time_in_force", "day").lower()
        
        if quantity <= 0 or not ticker:
            continue
            
        market_provider.add_ticker(ticker)
        
        if is_schwab:
            logger.info(f"Executing Schwab order: {side} {quantity} {ticker} {order_type}")
            res = schwab_service.place_order(acct_hash, ticker, quantity, side, order_type, limit_price, stop_price, tif)
            if not res.get("success"):
                logger.error(f"Schwab order failed: {res}")
            else:
                executed_orders.append(f"{side}:{quantity}:{ticker}")
        else:
            # Local execution with transaction (Simulated Paper Trading - Always Immediate Execution)
            with get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT cash_balance FROM accounts WHERE id = ?", (acct_id,))
                acct_row = cursor.fetchone()
                cash = acct_row[0] if acct_row else 0.0
                
                # Determine execution price
                current_price = price_cache.get(ticker)
                if current_price and current_price.get("price"):
                    market_price = current_price["price"]
                else:
                    real_p = fetch_real_market_price(ticker)
                    market_price = real_p if real_p is not None else 100.0
                    
                exec_price = limit_price if (limit_price and float(limit_price) > 0) else market_price
                total_cost = exec_price * quantity
                
                cursor.execute("SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND account_id = ? AND ticker = ?", (DEFAULT_USER_ID, acct_id, ticker))
                position = cursor.fetchone()
                pos_qty = position[0] if position else 0
                avg_cost = position[1] if position else 0
                
                now = datetime.now(UTC).isoformat()
                
                # Pre-trade validation: check funds for buy
                if side == "buy" and cash < total_cost:
                    logger.warning(f"Insufficient funds for local buy: {ticker} (requires ${total_cost:.2f}, available ${cash:.2f})")
                    failed_orders.append(f"{side}:{quantity}:{ticker}")
                    continue
                    
                # Insert order (Paper trade always fills immediately)
                order_id = str(uuid.uuid4())
                status = "FILLED"
                cursor.execute(
                    "INSERT INTO orders (id, user_id, account_id, ticker, side, quantity, order_type, limit_price, stop_price, time_in_force, status, broker_order_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (order_id, DEFAULT_USER_ID, acct_id, ticker, side, quantity, order_type.upper(), limit_price, stop_price, tif.upper(), status, None, now)
                )
                
                if status == "WORKING":
                    conn.commit()
                    continue
                
                if side == "buy":
                    new_cash = cash - total_cost
                    new_qty = pos_qty + quantity
                    new_avg = ((pos_qty * avg_cost) + total_cost) / new_qty if new_qty > 0 else 0
                    
                    cursor.execute("UPDATE accounts SET cash_balance = ? WHERE id = ?", (new_cash, acct_id))
                    
                    if position:
                        cursor.execute("UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? WHERE user_id = ? AND account_id = ? AND ticker = ?",
                                      (new_qty, new_avg, now, DEFAULT_USER_ID, acct_id, ticker))
                    else:
                        cursor.execute("INSERT INTO positions (id, user_id, account_id, ticker, quantity, avg_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                      (str(uuid.uuid4()), DEFAULT_USER_ID, acct_id, ticker, new_qty, new_avg, now))
                                      
                    cursor.execute("INSERT INTO trades (id, user_id, account_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                  (str(uuid.uuid4()), DEFAULT_USER_ID, acct_id, ticker, side, quantity, exec_price, now))
                    executed_orders.append(f"{side}:{quantity}:{ticker}")
                                  
                elif side == "sell":
                    new_cash = cash + total_cost
                    new_qty = pos_qty - quantity
                    
                    cursor.execute("UPDATE accounts SET cash_balance = ? WHERE id = ?", (new_cash, acct_id))
                    
                    if new_qty > 0:
                        cursor.execute("UPDATE positions SET quantity = ?, updated_at = ? WHERE user_id = ? AND account_id = ? AND ticker = ?",
                                      (new_qty, now, DEFAULT_USER_ID, acct_id, ticker))
                    else:
                        cursor.execute("DELETE FROM positions WHERE user_id = ? AND account_id = ? AND ticker = ?", (DEFAULT_USER_ID, acct_id, ticker))
                        
                    cursor.execute("INSERT INTO trades (id, user_id, account_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                  (str(uuid.uuid4()), DEFAULT_USER_ID, acct_id, ticker, side, quantity, exec_price, now))
                    executed_orders.append(f"{side}:{quantity}:{ticker}")
                
                conn.commit()

    return {
        "executed_watchlist": executed_watchlist,
        "failed_watchlist": failed_watchlist,
        "executed_orders": executed_orders,
        "failed_orders": failed_orders
    }
