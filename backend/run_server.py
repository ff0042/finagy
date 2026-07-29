import logging
import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Ensure both project root and backend directory are in sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = Path(__file__).resolve().parent
for p in [str(root_dir), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv(root_dir / ".env")
load_dotenv(backend_dir / ".env")

try:
    from backend.schwab_service import ensure_ssl_certs
except ModuleNotFoundError:
    from schwab_service import ensure_ssl_certs

if __name__ == "__main__":
    ensure_ssl_certs()
    cert = "db/cert.pem" if os.path.exists("db/cert.pem") else None
    key = "db/key.pem" if os.path.exists("db/key.pem") else None
    port = int(os.getenv("PORT", 8080))
    
    if cert and key:
        logging.info(f"Starting HTTPS Uvicorn Server on 0.0.0.0:{port} with SSL...")
        uvicorn.run("main:app", host="0.0.0.0", port=port, ssl_keyfile=key, ssl_certfile=cert)
    else:
        logging.info(f"Starting HTTP Uvicorn Server on 0.0.0.0:{port}...")
        uvicorn.run("main:app", host="0.0.0.0", port=port)
