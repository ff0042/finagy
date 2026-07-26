import os
import uvicorn
from backend.schwab_service import ensure_ssl_certs

if __name__ == "__main__":
    ensure_ssl_certs()
    cert = "db/cert.pem" if os.path.exists("db/cert.pem") else None
    key = "db/key.pem" if os.path.exists("db/key.pem") else None
    port = int(os.getenv("PORT", 8080))
    
    if cert and key:
        print(f"[INFO] Starting HTTPS Uvicorn Server on 0.0.0.0:{port} with SSL...")
        uvicorn.run("main:app", host="0.0.0.0", port=port, ssl_keyfile=key, ssl_certfile=cert)
    else:
        print(f"[INFO] Starting HTTP Uvicorn Server on 0.0.0.0:{port}...")
        uvicorn.run("main:app", host="0.0.0.0", port=port)
