import os
import json
import urllib.request

def create_pr():
    token = os.getenv("GITHUB_TOKEN", "")
    if not token and os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GITHUB_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not token:
        print("[ERROR] GITHUB_TOKEN not found in .env file.")
        return

    url = "https://api.github.com/repos/ff0042/finagy/pulls"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Antigravity-Agent"
    }

    body_content = ""
    if os.path.exists("PULL_REQUEST.md"):
        with open("PULL_REQUEST.md", "r", encoding="utf-8") as f:
            body_content = f.read()

    payload = {
        "title": "feat(v3): Multi-Account Selection & Schwab Developer API Integration",
        "head": "feature/v3-multi-account-schwab",
        "base": "main",
        "body": body_content
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[SUCCESS] Pull Request Created Successfully!")
            print(f"URL: {data.get('html_url')}")
    except urllib.error.HTTPError as e:
        print(f"[ERROR] GitHub API returned HTTP {e.code}: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"[ERROR] Failed to create Pull Request: {e}")

if __name__ == "__main__":
    create_pr()
