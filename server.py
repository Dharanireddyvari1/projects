__author__ = "Dharani Reddyvari"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import os
import random
import re
import threading
import time
from urllib.parse import urlparse, urlunparse

import httpx
from dotenv import load_dotenv  # reads variables from the .env file into os.environ
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from google_lens import get_exact_match_html  # the function that does the actual Lens scraping

# ---------------------------------------------------------------------------
# Load environment variables from .env file
# Must be called before any os.getenv() calls below
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# FastAPI app instance
# The title shows up in the auto-generated /docs Swagger UI
# ---------------------------------------------------------------------------
app = FastAPI(title="Google Lens Exact Match API")


# ---------------------------------------------------------------------------
# Proxy helpers
# ---------------------------------------------------------------------------

def parse_proxy_list(raw_value: str) -> list[str]:
    # Splits the PROXY_LIST string on commas or whitespace, strips stray quotes
    # Handles multiline or space-padded entries gracefully
    return [entry.strip().strip('"').strip("'") for entry in re.split(r"[\s,]+", raw_value) if entry.strip()]


def mask_proxy(proxy: str | None) -> str:
    # Hides credentials in proxy URLs before printing or returning them in API responses
    # e.g. http://user:pass@host:8001 → http://***:***@host:8001
    if not proxy:
        return "direct connection"

    parsed = urlparse(proxy)
    if "@" not in parsed.netloc:
        return proxy

    host = parsed.netloc.split("@", 1)[1]
    return urlunparse(parsed._replace(netloc=f"***:***@{host}"))


# ---------------------------------------------------------------------------
# Configuration — all values come from .env (or system environment variables)
# ---------------------------------------------------------------------------

RAW_PROXIES = os.getenv("PROXY_LIST", "")  # comma-separated list of proxy URLs
PROXIES = parse_proxy_list(RAW_PROXIES)    # parsed into a clean Python list

MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "5"))          # max simultaneous /google-lens requests
REQUEST_DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", "0.2"))  # minimum random delay (seconds) before each request
REQUEST_DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", "1.0"))  # maximum random delay (seconds) before each request
PROXY_HEALTH_URL = os.getenv("PROXY_HEALTH_URL", "https://ip.oxylabs.io/location")  # URL used to test proxy connectivity
REQUEST_SEMAPHORE = threading.Semaphore(MAX_CONCURRENCY)  # limits how many requests run at the same time

print(f"Loaded {len(PROXIES)} proxies")
print(f"Max concurrency: {MAX_CONCURRENCY}")


# ---------------------------------------------------------------------------
# Route: GET /health
# Quick liveness check — returns proxy count and concurrency limit
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "loaded_proxies": len(PROXIES), "max_concurrency": MAX_CONCURRENCY}


# ---------------------------------------------------------------------------
# Route: GET /proxy-health
# Tests every proxy in the pool against PROXY_HEALTH_URL
# Useful for verifying credentials and connectivity before running real requests
# ---------------------------------------------------------------------------
@app.get("/proxy-health")
def proxy_health():
    results = []

    for proxy in PROXIES:
        try:
            with httpx.Client(proxy=proxy, timeout=15) as client:
                response = client.get(PROXY_HEALTH_URL)
                response.raise_for_status()
            results.append({"proxy": mask_proxy(proxy), "ok": True, "status_code": response.status_code})
        except Exception as exc:
            results.append({"proxy": mask_proxy(proxy), "ok": False, "error": str(exc)})

    return {"count": len(results), "results": results}


# ---------------------------------------------------------------------------
# Route: GET /google-lens?imageUrl=...
# Main endpoint — takes a public image URL, runs it through Google Lens,
# and returns the Exact Match results page as raw HTML
# ---------------------------------------------------------------------------
@app.get("/google-lens", response_class=HTMLResponse)
def google_lens(imageUrl: str = Query(..., description="Public image URL to search")):
    # Basic validation — must be an http/https URL
    if not imageUrl.startswith("http"):
        raise HTTPException(status_code=400, detail="imageUrl must be a valid http/https URL")

    # Try to acquire a concurrency slot — rejects immediately if too many requests are in flight
    acquired = REQUEST_SEMAPHORE.acquire(blocking=False)
    if not acquired:
        raise HTTPException(status_code=429, detail="Too many concurrent requests. Try again shortly.")

    try:
        # Random delay before hitting Google to reduce bot detection likelihood
        if REQUEST_DELAY_MAX > 0:
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        # Call the scraping function — passes the full proxy pool so it can rotate on failure
        html = get_exact_match_html(imageUrl, proxies=PROXIES)
        return HTMLResponse(content=html, status_code=200)
    except RuntimeError as e:
        # Known failure from google_lens.py (proxy failure, bot block, bad redirect, etc.)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        # Unexpected failure — should not normally happen
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
    finally:
        # Always release the semaphore slot, even if an exception was raised
        REQUEST_SEMAPHORE.release()


# ---------------------------------------------------------------------------
# Entry point — only used when running directly: python -m server
# (not used when uvicorn is started externally)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, workers=1)
