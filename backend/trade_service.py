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
            
    is_schwab = schwab_service.get_token_status().get("authenticated", False) and acct_hash

    # Process Trades
    for t in trades:
        ticker = t.get("ticker", "").upper()
        side = t.get("side", "").lower()
        quantity = float(t.get("quantity", 0))
        
        if quantity <= 0 or not ticker:
            continue
            
        market_provider.add_ticker(ticker)
        
        if is_schwab:
            # Execute via Schwab API only, no local DB writes
            logger.info(f"Executing Schwab order: {side} {quantity} {ticker}")
            res = schwab_service.place_market_order(acct_hash, ticker, quantity, side)
            if not res.get("success"):
                logger.error(f"Schwab market order failed: {res}")
        else:
            # Local execution with transaction
            with get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT cash_balance FROM accounts WHERE id = ?", (acct_id,))
                acct_row = cursor.fetchone()
                cash = acct_row[0] if acct_row else 0.0
                
                current_price = price_cache.get(ticker)
                price = current_price["price"] if current_price else 150.0
                total_cost = price * quantity
                
                cursor.execute("SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND account_id = ? AND ticker = ?", (DEFAULT_USER_ID, acct_id, ticker))
                position = cursor.fetchone()
                pos_qty = position[0] if position else 0
                avg_cost = position[1] if position else 0
                
                now = datetime.now(timezone.utc).isoformat()
                
                if side == "buy":
                    if cash < total_cost:
                        logger.warning(f"Insufficient funds for local buy: {ticker}")
                        continue
                    
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
                                  (str(uuid.uuid4()), DEFAULT_USER_ID, acct_id, ticker, side, quantity, price, now))
                                  
                elif side == "sell":
                    if pos_qty < quantity:
                        logger.warning(f"Insufficient position for local sell: {ticker}")
                        continue
                        
                    new_cash = cash + total_cost
                    new_qty = pos_qty - quantity
                    
                    cursor.execute("UPDATE accounts SET cash_balance = ? WHERE id = ?", (new_cash, acct_id))
                    
                    if new_qty > 0:
                        cursor.execute("UPDATE positions SET quantity = ?, updated_at = ? WHERE user_id = ? AND account_id = ? AND ticker = ?",
                                      (new_qty, now, DEFAULT_USER_ID, acct_id, ticker))
                    else:
                        cursor.execute("DELETE FROM positions WHERE user_id = ? AND account_id = ? AND ticker = ?", (DEFAULT_USER_ID, acct_id, ticker))
                        
                    cursor.execute("INSERT INTO trades (id, user_id, account_id, ticker, side, quantity, price, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                  (str(uuid.uuid4()), DEFAULT_USER_ID, acct_id, ticker, side, quantity, price, now))
                
                conn.commit()
