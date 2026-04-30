__author__ = "Dharani Reddyvari"

import os
import random
import re
import threading
import time
from urllib.parse import urlparse, urlunparse

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from google_lens import get_exact_match_html


load_dotenv()

app = FastAPI(title="Google Lens Exact Match API")


def parse_proxy_list(raw_value: str) -> list[str]:
    return [entry.strip().strip('"').strip("'") for entry in re.split(r"[\s,]+", raw_value) if entry.strip()]


def mask_proxy(proxy: str | None) -> str:
    if not proxy:
        return "direct connection"

    parsed = urlparse(proxy)
    if "@" not in parsed.netloc:
        return proxy

    host = parsed.netloc.split("@", 1)[1]
    return urlunparse(parsed._replace(netloc=f"***:***@{host}"))


RAW_PROXIES = os.getenv("PROXY_LIST", "")
PROXIES = parse_proxy_list(RAW_PROXIES)

MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "5"))
REQUEST_DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", "0.2"))
REQUEST_DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", "1.0"))
PROXY_HEALTH_URL = os.getenv("PROXY_HEALTH_URL", "https://ip.oxylabs.io/location")
REQUEST_SEMAPHORE = threading.Semaphore(MAX_CONCURRENCY)

print(f"Loaded {len(PROXIES)} proxies")
print(f"Max concurrency: {MAX_CONCURRENCY}")


@app.get("/health")
def health():
    return {"status": "ok", "loaded_proxies": len(PROXIES), "max_concurrency": MAX_CONCURRENCY}


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


@app.get("/google-lens", response_class=HTMLResponse)
def google_lens(imageUrl: str = Query(..., description="Public image URL to search")):
    if not imageUrl.startswith("http"):
        raise HTTPException(status_code=400, detail="imageUrl must be a valid http/https URL")

    acquired = REQUEST_SEMAPHORE.acquire(blocking=False)
    if not acquired:
        raise HTTPException(status_code=429, detail="Too many concurrent requests. Try again shortly.")

    try:
        if REQUEST_DELAY_MAX > 0:
            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        html = get_exact_match_html(imageUrl, proxies=PROXIES)
        return HTMLResponse(content=html, status_code=200)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
    finally:
        REQUEST_SEMAPHORE.release()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, workers=1)
