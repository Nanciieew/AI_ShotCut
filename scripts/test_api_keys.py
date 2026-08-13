"""Quick API connectivity test for all pipeline models."""

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# 1. DeepSeek API
print("=== DeepSeek API ===")
key = os.getenv("DEEPSEEK_API_KEY", "")
print(f"Key configured: {bool(key)}")
try:
    r = requests.get(
        "https://api.modelarts-maas.com/v1/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=10,
    )
    print(f"Status: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")

# 2. Doubao Vision API
print("\n=== Doubao Vision API (Volcano Ark) ===")
vision_key = os.getenv("VOLC_VISION_API_KEY", "")
print(f"Key configured: {bool(vision_key)}")
try:
    r = requests.get(
        "https://ark.cn-beijing.volces.com/api/v3/models",
        headers={"Authorization": f"Bearer {vision_key}"},
        timeout=10,
    )
    print(f"Status: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")

# 3. Doubao ASR API
print("\n=== Doubao SeedASR API ===")
app_id = os.getenv("VOLC_APP_ID", "")
token = os.getenv("VOLC_ACCESS_TOKEN", "")
print(f"APP_ID configured: {bool(app_id)}, token configured: {bool(token)}")
try:
    r = requests.post(
        "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query",
        json={},
        headers={
            "X-Api-App-Key": app_id,
            "X-Api-Access-Key": token,
            "X-Api-Resource-Id": "volc.seedasr.auc",
            "X-Api-Request-Id": "test-connectivity-check",
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    print(f"Status: {r.status_code}")
    sc = r.headers.get("X-Api-Status-Code", "")
    print(f"X-Api-Status-Code: {sc} ({'OK' if sc == '20000000' else 'auth valid'})")
except Exception as e:
    print(f"Error: {e}")

# 4. Public URL for Doubao ASR audio
print("\n=== Audio Public URL ===")
public_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
print(f"PUBLIC_BASE_URL: {public_url}")
print("SeedASR needs public URL — localhost won't work. Use ngrok or public server.")
