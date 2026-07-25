import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

class SchwabService:
    """High-level Schwab Developer API service for account management, positions, and order execution."""
    
    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        app_key = os.getenv("SCHWAB_CLIENT_ID") or os.getenv("SCHWAB_APP_KEY")
        app_secret = os.getenv("SCHWAB_CLIENT_SECRET") or os.getenv("SCHWAB_APP_SECRET")
        callback_url = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1:8080")
        tokens_db = os.getenv("SCHWAB_TOKENS_DB", "db/tokens.db")

        if not app_key or not app_secret:
            return

        tokens_path = Path(tokens_db)
        tokens_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import schwabdev
            self.client = schwabdev.Client(
                app_key=app_key,
                app_secret=app_secret,
                callback_url=callback_url,
                tokens_db=str(tokens_path)
            )
        except Exception as e:
            print(f"[WARN] schwabdev initialization: {e}")
            self.client = None

    def get_linked_accounts(self) -> List[Dict[str, Any]]:
        """Fetch linked accounts via client.account_linked()."""
        if not self.client:
            return []
        try:
            resp = self.client.account_linked()
            if resp and resp.status_code == 200:
                data = resp.json()
                accounts = []
                for idx, item in enumerate(data):
                    acct_num = str(item.get("accountNumber", ""))
                    acct_hash = item.get("hashValue", "")
                    suffix = acct_num[-4:] if len(acct_num) >= 4 else f"{idx+1}"
                    accounts.append({
                        "id": f"schwab_{acct_hash[:8]}",
                        "account_number": acct_num,
                        "account_hash": acct_hash,
                        "name": f"SCHWAB_ACCT_{suffix}",
                        "type": "SCHWAB",
                        "is_active": 1 if idx == 0 else 0,
                        "cash_balance": 10000.0
                    })
                return accounts
        except Exception as e:
            print(f"[WARN] Error fetching linked accounts: {e}")
        return []

    def get_account_details(self, account_hash: str) -> Optional[Dict[str, Any]]:
        """Fetch account positions and balances via client.account_details()."""
        if not self.client:
            return None
        try:
            resp = self.client.account_details(account_hash, fields="positions")
            if resp and resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"[WARN] Error fetching account details: {e}")
        return None

    def place_market_order(self, account_hash: str, ticker: str, quantity: float, side: str) -> Dict[str, Any]:
        """Place an equity market order via client.order_place()."""
        if not self.client:
            return {"success": False, "error": "Schwab client not initialized"}
            
        instruction = "BUY" if side.lower() == "buy" else "SELL"
        order_spec = {
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": instruction,
                    "quantity": int(quantity),
                    "instrument": {
                        "symbol": ticker.upper(),
                        "assetType": "EQUITY"
                    }
                }
            ]
        }
        
        try:
            resp = self.client.order_place(account_hash, order_spec)
            if resp and resp.status_code in (200, 201):
                return {"success": True, "response": resp.json() if resp.content else "Order submitted"}
            return {"success": False, "status_code": resp.status_code, "text": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

schwab_service = SchwabService()
