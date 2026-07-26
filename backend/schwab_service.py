import os
import json
import ssl
import threading
import urllib.parse
import sqlite3
import base64
import requests
import datetime
import time
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, List, Optional
import ipaddress

# Resolve persistent DB path (survives container restarts)
if os.path.exists("/app/db"):
    DB_DIR = Path("/app/db")
else:
    DB_DIR = Path(__file__).parent.parent / "db"

TOKENS_DB_PATH = DB_DIR / "tokens.db"
TOKENS_FILE_PATH = DB_DIR / "tokens.json"

def ensure_ssl_certs():
    """Ensure self-signed SSL certificates exist for HTTPS callback listener on port 8080."""
    cert_path = DB_DIR / "cert.pem"
    key_path = DB_DIR / "key.pem"
    if cert_path.exists() and key_path.exists():
        return True

    DB_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "FinAlly Workstation")
        ])
        san = x509.SubjectAlternativeName([
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            x509.DNSName("localhost")
        ])

        now = datetime.datetime.now(datetime.timezone.utc)
        cert = x509.CertificateBuilder().subject_name(
            name
        ).issuer_name(
            name
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            now - datetime.timedelta(days=1)
        ).not_valid_after(
            now + datetime.timedelta(days=365)
        ).add_extension(
            san, critical=False
        ).sign(key, hashes.SHA256())

        key_path.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        ))
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        return True
    except Exception as e:
        print(f"[WARN] Failed to generate SSL certificates: {e}")
        return False

class SchwabService:
    """High-level Schwab Developer API service for OAuth PKCE authentication, account management, positions, and orders."""
    
    def __init__(self):
        self.client = None
        self._linked_accts_cache = None
        self._linked_accts_ts = 0.0
        self._acct_details_cache = {}
        self._init_client()

    def _init_client(self):
        app_key = os.getenv("SCHWAB_CLIENT_ID") or os.getenv("SCHWAB_APP_KEY")
        app_secret = os.getenv("SCHWAB_CLIENT_SECRET") or os.getenv("SCHWAB_APP_SECRET")
        callback_url = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1:8080")

        if not app_key or not app_secret:
            return

        TOKENS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        has_valid_db_token = False
        if TOKENS_DB_PATH.exists():
            try:
                conn = sqlite3.connect(str(TOKENS_DB_PATH))
                cur = conn.cursor()
                cur.execute("SELECT access_token, refresh_token, refresh_token_issued FROM schwabdev LIMIT 1")
                row = cur.fetchone()
                conn.close()
                if row and row[0] and row[1] and row[2]:
                    issued_str = row[2].replace("Z", "+00:00")
                    issued_dt = datetime.datetime.fromisoformat(issued_str)
                    if issued_dt.tzinfo is None:
                        issued_dt = issued_dt.replace(tzinfo=datetime.timezone.utc)
                    now_dt = datetime.datetime.now(datetime.timezone.utc)
                    # Refresh tokens expire after 7 days
                    if (now_dt - issued_dt).total_seconds() < 6.5 * 86400:
                        has_valid_db_token = True
            except Exception:
                pass

        has_valid_file_token = False
        if TOKENS_FILE_PATH.exists():
            try:
                with open(TOKENS_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    issued_str = data.get("refresh_token_issued", "")
                    toks = data.get("token_dictionary", {})
                    if toks.get("access_token") and toks.get("refresh_token") and issued_str:
                        issued_str = issued_str.replace("Z", "+00:00")
                        issued_dt = datetime.datetime.fromisoformat(issued_str)
                        if issued_dt.tzinfo is None:
                            issued_dt = issued_dt.replace(tzinfo=datetime.timezone.utc)
                        now_dt = datetime.datetime.now(datetime.timezone.utc)
                        if (now_dt - issued_dt).total_seconds() < 6.5 * 86400:
                            has_valid_file_token = True
            except Exception:
                pass

        if not has_valid_db_token and not has_valid_file_token:
            self.client = None
            return

        try:
            import schwabdev
            try:
                self.client = schwabdev.Client(
                    app_key=app_key,
                    app_secret=app_secret,
                    callback_url=callback_url,
                    tokens_db=str(TOKENS_DB_PATH),
                    open_browser_for_auth=False
                )
            except TypeError:
                self.client = schwabdev.Client(
                    app_key=app_key,
                    app_secret=app_secret,
                    callback_url=callback_url,
                    tokens_file=str(TOKENS_FILE_PATH)
                )
        except Exception as e:
            print(f"[WARN] schwabdev initialization: {e}")
            self.client = None

    def get_auth_url(self) -> str:
        """Construct official Schwab OAuth authorization URL for browser login."""
        app_key = os.getenv("SCHWAB_CLIENT_ID") or os.getenv("SCHWAB_APP_KEY", "")
        callback_url = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1:8080")
        params = {
            "response_type": "code",
            "client_id": app_key,
            "redirect_uri": callback_url
        }
        return f"https://api.schwabapi.com/v1/oauth/authorize?{urllib.parse.urlencode(params)}"

    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code directly for tokens and write to persistent TOKENS_DB_PATH and TOKENS_FILE_PATH."""
        app_key = os.getenv("SCHWAB_CLIENT_ID") or os.getenv("SCHWAB_APP_KEY")
        app_secret = os.getenv("SCHWAB_CLIENT_SECRET") or os.getenv("SCHWAB_APP_SECRET")
        callback_url = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1:8080")

        if not app_key or not app_secret:
            return {"success": False, "error": "App credentials missing"}

        raw_code = urllib.parse.unquote(code)

        auth_str = base64.b64encode(f"{app_key}:{app_secret}".encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "grant_type": "authorization_code",
            "code": raw_code,
            "redirect_uri": callback_url
        }

        try:
            resp = requests.post("https://api.schwabapi.com/v1/oauth/token", data=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                tokens_dict = resp.json()
                self._write_tokens_to_db(TOKENS_DB_PATH, tokens_dict)
                self._write_tokens_to_file(TOKENS_FILE_PATH, tokens_dict)
                self._init_client()
                return {"success": True, "tokens": tokens_dict}
            else:
                print(f"[WARN] Token exchange failed HTTP {resp.status_code}: {resp.text}")
                return {"success": False, "status_code": resp.status_code, "error": resp.text}
        except Exception as e:
            print(f"[WARN] Token exchange exception: {e}")
            return {"success": False, "error": str(e)}

    def _write_tokens_to_db(self, tokens_db_path: Path, tokens_data: dict):
        """Direct SQLite writer matching schwabdev table schema exactly."""
        try:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn = sqlite3.connect(str(tokens_db_path))
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS schwabdev (
                access_token_issued TEXT NOT NULL,
                refresh_token_issued TEXT NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                id_token TEXT NOT NULL,
                expires_in INTEGER,
                token_type TEXT,
                scope TEXT
            );
            """)
            cur.execute("DELETE FROM schwabdev;")
            cur.execute("""
            INSERT INTO schwabdev (
                access_token_issued,
                refresh_token_issued,
                access_token,
                refresh_token,
                id_token,
                expires_in,
                token_type,
                scope
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                now,
                now,
                tokens_data.get("access_token", ""),
                tokens_data.get("refresh_token", ""),
                tokens_data.get("id_token", ""),
                tokens_data.get("expires_in", 1800),
                tokens_data.get("token_type", "Bearer"),
                tokens_data.get("scope", "api")
            ))
            conn.commit()
            conn.close()
            print(f"[SUCCESS] Successfully saved OAuth tokens into persistent {tokens_db_path} (table schwabdev).")
        except Exception as e:
            print(f"[WARN] Failed to write tokens to DB: {e}")

    def _write_tokens_to_file(self, tokens_file_path: Path, tokens_data: dict):
        """Write JSON format matching schwabdev token specification."""
        try:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            formatted = {
                "access_token_issued": now_iso,
                "refresh_token_issued": now_iso,
                "token_dictionary": tokens_data
            }
            tokens_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tokens_file_path, "w", encoding="utf-8") as f:
                json.dump(formatted, f, indent=4)
            print(f"[SUCCESS] Successfully saved OAuth tokens into persistent {tokens_file_path}")
        except Exception as e:
            print(f"[WARN] Failed to write tokens to file: {e}")

    def disconnect(self) -> bool:
        """Clear saved Schwab tokens and reset active client."""
        self.client = None
        try:
            if TOKENS_DB_PATH.exists():
                try:
                    conn = sqlite3.connect(str(TOKENS_DB_PATH))
                    cur = conn.cursor()
                    cur.execute("DROP TABLE IF EXISTS schwabdev;")
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
            if TOKENS_FILE_PATH.exists():
                try:
                    os.remove(TOKENS_FILE_PATH)
                except Exception:
                    pass
            print("[INFO] Successfully disconnected and cleared Schwab tokens")
            return True
        except Exception as e:
            print(f"[WARN] Error disconnecting Schwab tokens: {e}")
            return False

    def get_token_status(self) -> Dict[str, Any]:
        """Check if client is active and tokens are valid."""
        if not self.client:
            return {"authenticated": False, "reason": "Client not initialized or credentials missing"}
            
        try:
            fetch_fn = getattr(self.client, 'linked_accounts', getattr(self.client, 'account_linked', None))
            if not fetch_fn:
                return {"authenticated": False, "reason": "linked_accounts function missing"}
            resp = fetch_fn()
            if resp and resp.status_code == 200:
                accounts = resp.json()
                return {
                    "authenticated": True,
                    "account_count": len(accounts),
                    "status": "connected"
                }
            return {
                "authenticated": False,
                "status_code": resp.status_code if resp else None,
                "reason": "Token expired or unauthorized"
            }
        except Exception as e:
            return {"authenticated": False, "reason": str(e)}

    def get_linked_accounts(self) -> List[Dict[str, Any]]:
        """Fetch linked accounts via client.linked_accounts() and hydrate real cash balances."""
        if not self.client:
            return []
            
        now_time = time.time()
        if self._linked_accts_cache is not None and (now_time - self._linked_accts_ts) < 10.0:
            return self._linked_accts_cache

        try:
            fetch_fn = getattr(self.client, 'linked_accounts', getattr(self.client, 'account_linked', None))
            if not fetch_fn: return []
            resp = fetch_fn()
            if resp and resp.status_code == 200:
                data = resp.json()
                accounts = []
                for idx, item in enumerate(data):
                    acct_num = str(item.get("accountNumber", ""))
                    acct_hash = item.get("hashValue", "")
                    suffix = acct_num[-4:] if len(acct_num) >= 4 else f"{idx+1}"
                    
                    cash_bal = 0.0
                    try:
                        details = self.get_account_details(acct_hash)
                        if details and "securitiesAccount" in details:
                            balances = details.get("securitiesAccount", {}).get("currentBalances", {})
                            cash_bal = balances.get("cashBalance", 0.0)
                    except Exception as ex:
                        print(f"[WARN] Error fetching cash balance for account {acct_num}: {ex}")

                    accounts.append({
                        "id": f"schwab_{acct_hash[:8]}",
                        "account_number": acct_num,
                        "account_hash": acct_hash,
                        "name": f"SCHWAB_ACCT_{suffix}",
                        "type": "SCHWAB",
                        "is_active": 1 if idx == 0 else 0,
                        "cash_balance": cash_bal
                    })
                self._linked_accts_cache = accounts
                self._linked_accts_ts = now_time
                return accounts
        except Exception as e:
            print(f"[WARN] Error fetching linked accounts: {e}")
        return []

    def get_account_details(self, account_hash: str) -> Optional[Dict[str, Any]]:
        """Fetch account positions and balances via client.account_details()."""
        if not self.client:
            return None

        now_time = time.time()
        if account_hash in self._acct_details_cache:
            ts, cached_data = self._acct_details_cache[account_hash]
            if (now_time - ts) < 10.0:
                return cached_data

        try:
            resp = self.client.account_details(account_hash, fields="positions")
            if resp and resp.status_code == 200:
                data = resp.json()
                self._acct_details_cache[account_hash] = (now_time, data)
                return data
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
            place_fn = getattr(self.client, 'place_order', getattr(self.client, 'order_place', None))
            if not place_fn: return {"success": False, "error": "Order place function missing"}
            resp = place_fn(account_hash, order_spec)
            if resp and resp.status_code in (200, 201):
                return {"success": True, "response": resp.json() if resp.content else "Order submitted"}
            return {"success": False, "status_code": resp.status_code, "text": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

schwab_service = SchwabService()
