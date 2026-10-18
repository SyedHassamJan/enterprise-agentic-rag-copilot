"""Container health probe used by the Docker HEALTHCHECK (exit 0 = healthy, 1 = unhealthy).

Uses only the standard library, so the slim image needs no curl/wget.
"""
import os
import sys
import urllib.request

url = f"http://127.0.0.1:{os.environ.get('PORT', '8080')}/api/health"
try:
    with urllib.request.urlopen(url, timeout=4) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
