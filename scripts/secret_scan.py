#!/usr/bin/env python3
"""
Pre-commit / Pre-push Secret Scanner for Finagy.
Scans staged git files for potential secret keys, API tokens, credentials, and personal designators.
"""

import sys
import re
import subprocess

# Secret and Personal Designator patterns to detect
PATTERNS = [
    (r"sk-[a-zA-Z0-9]{32,}", "OpenAI API Key"),
    (r"sk-or-[a-zA-Z0-9]{32,}", "OpenRouter API Key"),
    (r"SCHWAB_CLIENT_SECRET\s*=\s*['\"]?[A-Za-z0-9]{12,}['\"]?", "Schwab Client Secret"),
    (r"SCHWAB_CLIENT_ID\s*=\s*['\"]?[A-Za-z0-9]{16,}['\"]?", "Schwab Client ID"),
    (r"MASSIVE_API_KEY\s*=\s*['\"]?[A-Za-z0-9]{16,}['\"]?", "Massive / Polygon API Key"),
    (r"-----BEGIN (RSA|OPENSSH|EC|PGP) PRIVATE KEY-----", "Private Cryptographic Key"),
    (r"\"refresh_token\"\s*:\s*\"[^\"]{20,}\"", "OAuth Refresh Token"),
    (r"\"access_token\"\s*:\s*\"[^\"]{20,}\"", "OAuth Access Token"),
    (r"FF42", "Personal Designator Identifier"),
]

# File patterns to exclude from scanning
EXCLUDED_FILES = [
    ".git",
    "uv.lock",
    "package-lock.json",
    "scripts/secret_scan.py",
    ".gitignore",
]

def get_staged_files():
    try:
        out = subprocess.check_output(["git", "diff", "--cached", "--name-only"], text=True)
        return [f.strip() for f in out.splitlines() if f.strip()]
    except Exception:
        return []

def scan_file(filepath):
    # Skip excluded files or non-existent files
    if any(ex in filepath for ex in EXCLUDED_FILES):
        return []

    findings = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            for idx, line in enumerate(lines, 1):
                # Ignore placeholder values
                if "your-" in line.lower() or "placeholder" in line.lower() or "example" in line.lower():
                    continue
                for pattern, name in PATTERNS:
                    if re.search(pattern, line):
                        findings.append((idx, name, line.strip()))
    except Exception:
        pass
    return findings

def main():
    staged_files = get_staged_files()
    if not staged_files:
        sys.exit(0)

    total_findings = 0
    print("[SECRET SCANNER] Scanning staged files for sensitive credentials...")

    for filepath in staged_files:
        findings = scan_file(filepath)
        if findings:
            total_findings += len(findings)
            print(f"\n[ALERT] Potential secret or personal designator detected in file: {filepath}")
            for line_no, secret_type, snippet in findings:
                masked_snippet = snippet[:15] + "..." + snippet[-10:] if len(snippet) > 30 else snippet
                print(f"   Line {line_no} ({secret_type}): {masked_snippet}")

    if total_findings > 0:
        print("\n" + "=" * 70)
        print("[ERROR] COMMIT BLOCKED: Potential sensitive information or personal designator detected.")
        print("Please sanitize the file(s) before committing or pushing.")
        print("If this is a false positive, verify manually and update scripts/secret_scan.py.")
        print("=" * 70 + "\n")
        sys.exit(1)

    print("[SUCCESS] No sensitive secrets detected in staged files.\n")
    sys.exit(0)

if __name__ == "__main__":
    main()
