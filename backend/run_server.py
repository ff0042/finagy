import os
import uvicorn
from schwab_service import ensure_ssl_certs

if __name__ == "__main__":
    ensure_ssl_certs()
    cert = "db/cert.pem" if os.path.exists("db/cert.pem") else None
    key = "db/key.pem" if os.path.exists("db/key.pem") else None
    
    if cert and key:
        print("[INFO] Starting HTTPS Uvicorn Server on 0.0.0.0:8000 with SSL...")
        uvicorn.run("main:app", host="0.0.0.0", port=8000, ssl_keyfile=key, ssl_certfile=cert)
    else:
        print("[INFO] Starting HTTP Uvicorn Server on 0.0.0.0:8000...")
        uvicorn.run("main:app", host="0.0.0.0", port=8000)
