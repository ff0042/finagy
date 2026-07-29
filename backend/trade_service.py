import uuid
import logging
from datetime import datetime, timezone
from backend.db.database import get_connection, execute_query, get_active_account
from backend.market_data import get_market_data_provider, price_cache
from backend.schwab_service import schwab_service
from backend.constants import DEFAULT_USER_ID, DEFAULT_ACCOUNT_ID

logger = logging.getLogger(__name__)

def execute_actions(response_data, account_id=None):
    trades = response_data.get("trades", [])
    watchlist_changes = response_data.get("watchlist_changes", [])
    
    market_provider = get_market_data_provider()
    
    if not account_id:
        active_acct = get_active_account()
        acct_id = active_acct["id"] if active_acct else DEFAULT_ACCOUNT_ID
        acct_type = active_acct["type"] if active_acct else "LOCAL"
        acct_hash = active_acct.get("account_hash") if active_acct else None
    else:
        acct_id = account_id
        # Need to fetch account type
        rows = execute_query("SELECT type, account_hash FROM accounts WHERE id = ?", (acct_id,))
        acct_type = rows[0]["type"] if rows else "LOCAL"
        acct_hash = rows[0]["account_hash"] if rows else None

    # Process Watchlist (Always local)
    for w in watchlist_changes:
        ticker = w.get("ticker", "").upper()
        action = w.get("action", "").lower()
        if not ticker:
            continue
        if action == "add":
            try:
                execute_query(
                    "INSERT INTO watchlist (id, user_id, account_id, ticker, added_at) VALUES (?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), DEFAULT_USER_ID, acct_id, ticker, datetime.now(timezone.utc).isoformat())
                )
            except Exception as e:
                logger.warning(f"Failed to add {ticker} to watchlist: {e}")
            market_provider.add_ticker(ticker)
        elif action == "remove":
            execute_query(
                "DELETE FROM watchlist WHERE user_id = ? AND account_id = ? AND ticker = ?",
                (DEFAULT_USER_ID, acct_id, ticker)
            )
            
    is_schwab = (acct_type == "SCHWAB") and schwab_service.get_token_status().get("authenticated", False) and acct_hash

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
                    # Mark canceled in DB
                    execute_query("UPDATE orders SET status = 'CANCELED', updated_at = ? WHERE broker_order_id = ?", 
                                  (datetime.now(timezone.utc).isoformat(), order_id))
            else:
                # Cancel local order
                execute_query("UPDATE orders SET status = 'CANCELED', updated_at = ? WHERE id = ?", 
                              (datetime.now(timezone.utc).isoformat(), order_id))
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
                broker_order_id = res.get("order_id", "UNKNOWN")
                status = "WORKING" if order_type != "market" else "FILLED"
                # Insert into local orders table
                execute_query(
                    "INSERT INTO orders (id, user_id, account_id, ticker, side, quantity, order_type, limit_price, stop_price, time_in_force, status, broker_order_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), DEFAULT_USER_ID, acct_id, ticker, side, quantity, order_type.upper(), limit_price, stop_price, tif.upper(), status, broker_order_id, datetime.now(timezone.utc).isoformat())
                )
        else:
            # Local execution with transaction
            with get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT cash_balance FROM accounts WHERE id = ?", (acct_id,))
                acct_row = cursor.fetchone()
                cash = acct_row[0] if acct_row else 0.0
                
                # Determine execution price
                current_price = price_cache.get(ticker)
                market_price = current_price["price"] if current_price else 150.0
                exec_price = limit_price if limit_price else market_price
                total_cost = exec_price * quantity
                
                cursor.execute("SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND account_id = ? AND ticker = ?", (DEFAULT_USER_ID, acct_id, ticker))
                position = cursor.fetchone()
                pos_qty = position[0] if position else 0
                avg_cost = position[1] if position else 0
                
                now = datetime.now(timezone.utc).isoformat()
                
                # Pre-trade validation
                if side == "buy" and cash < total_cost:
                    logger.warning(f"Insufficient funds for local buy: {ticker}")
                    continue
                if side == "sell" and pos_qty < quantity:
                    logger.warning(f"Insufficient position for local sell: {ticker}")
                    continue
                    
                # Insert order
                order_id = str(uuid.uuid4())
                status = "WORKING" if order_type != "market" else "FILLED"
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
                
                conn.commit()
