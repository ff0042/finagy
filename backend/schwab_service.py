import os
import json
import ssl
import threading
import urllib.parse
import sqlite3
import base64
import requests
import datetime
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
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
        san = x509.SubjectAlternativeName([
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            x509.DNSName("localhost")
        ])

        cert = x509.CertificateBuilder().subject_name(
            name
        ).issuer_name(
            name
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow() - datetime.timedelta(days=1)
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
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

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        code = query.get('code', [None])[0]
        
        if code:
            schwab_service.exchange_code_for_tokens(code)
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Schwab Authorization Successful</title>
                <style>
                    body { background-color: #0d1117; color: #ffffff; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                    .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 2rem; text-align: center; max-width: 400px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
                    h2 { color: #2ea043; margin-top: 0; }
                    p { color: #8b949e; font-size: 14px; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>Schwab Connected!</h2>
                    <p>Your authentication tokens have been updated successfully.</p>
                    <p>You can close this window and return to FinAlly workstation.</p>
                </div>
                <script>
                    if (window.opener) {
                        try { window.opener.postMessage("schwab-auth-success", "*"); } catch(e) {}
                        setTimeout(() => window.close(), 2500);
                    }
                </script>
            </body>
            </html>
            """
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        else:
            self.send_response(400)
            self.end_headers()

def start_https_listener():
    if not ensure_ssl_certs():
        return
    try:
        cert_path = DB_DIR / "cert.pem"
        key_path = DB_DIR / "key.pem"
        server = HTTPServer(('0.0.0.0', 8080), OAuthCallbackHandler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        print("[INFO] Started HTTPS OAuth Callback Listener on port 8080.")
    except Exception as e:
        print(f"[WARN] HTTPS listener start error: {e}")

class SchwabService:
    """High-level Schwab Developer API service for OAuth PKCE authentication, account management, positions, and orders."""
    
    def __init__(self):
        self.client = None
        self._init_client()
        start_https_listener()

    def _init_client(self):
        app_key = os.getenv("SCHWAB_CLIENT_ID") or os.getenv("SCHWAB_APP_KEY")
        app_secret = os.getenv("SCHWAB_CLIENT_SECRET") or os.getenv("SCHWAB_APP_SECRET")
        callback_url = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1:8080")

        if not app_key or not app_secret:
            return

        TOKENS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        try:
            import schwabdev
            self.client = schwabdev.Client(
                app_key=app_key,
                app_secret=app_secret,
                callback_url=callback_url,
                tokens_db=str(TOKENS_DB_PATH),
                open_browser_for_auth=False
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
        """Exchange authorization code directly for tokens and write to persistent TOKENS_DB_PATH."""
        app_key = os.getenv("SCHWAB_CLIENT_ID") or os.getenv("SCHWAB_APP_KEY")
        app_secret = os.getenv("SCHWAB_CLIENT_SECRET") or os.getenv("SCHWAB_APP_SECRET")
        callback_url = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1:8080")

        if not app_key or not app_secret:
            return {"success": False, "error": "App credentials missing"}

        auth_str = base64.b64encode(f"{app_key}:{app_secret}".encode("utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": callback_url
        }

        try:
            resp = requests.post("https://api.schwabapi.com/v1/oauth/token", data=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                tokens_dict = resp.json()
                self._write_tokens_to_db(str(TOKENS_DB_PATH), tokens_dict)
                self._init_client()
                return {"success": True, "tokens": tokens_dict}
            else:
                print(f"[WARN] Token exchange failed HTTP {resp.status_code}: {resp.text}")
                return {"success": False, "status_code": resp.status_code, "error": resp.text}
        except Exception as e:
            print(f"[WARN] Token exchange exception: {e}")
            return {"success": False, "error": str(e)}

    def _write_tokens_to_db(self, tokens_db_path: str, tokens_data: dict):
        """Direct SQLite writer matching schwabdev table schema exactly."""
        try:
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            conn = sqlite3.connect(tokens_db_path)
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

    def disconnect(self) -> bool:
        """Clear saved Schwab tokens and reset active client."""
        self.client = None
        try:
            if TOKENS_DB_PATH.exists():
                conn = sqlite3.connect(str(TOKENS_DB_PATH))
                cur = conn.cursor()
                cur.execute("DROP TABLE IF EXISTS schwabdev;")
                conn.commit()
                conn.close()
                print(f"[INFO] Successfully disconnected and cleared Schwab tokens from {TOKENS_DB_PATH}")
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
            place_fn = getattr(self.client, 'place_order', getattr(self.client, 'order_place', None))
            if not place_fn: return {"success": False, "error": "Order place function missing"}
            resp = place_fn(account_hash, order_spec)
            if resp and resp.status_code in (200, 201):
                return {"success": True, "response": resp.json() if resp.content else "Order submitted"}
            return {"success": False, "status_code": resp.status_code, "text": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

schwab_service = SchwabService()
