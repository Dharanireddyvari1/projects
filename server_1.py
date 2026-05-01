__author__ = "Dharani Reddyvari"

import os
import random
import re
import threading
import time
import uvicorn


from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from google_lens_1 import exact_match_html

load_dotenv()

# FastAPI app instance
app = FastAPI(title="Google Lens Exact Match API")

# Final Proxy List
PROXIES = []
RAW_PROXIES = os.getenv("PROXY_LIST", "")
for i in re.split(r"[\s,]+", RAW_PROXIES):
    i = i.strip().strip("\"'")
    if i:
        PROXIES.append(i)

# Concurrency limit and request throttling settings
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "5"))
REQUEST_DELAY_MIN = float(os.getenv("REQUEST_DELAY_MIN", "0.2"))
REQUEST_DELAY_MAX = float(os.getenv("REQUEST_DELAY_MAX", "1.0"))
SEMAPHORE = threading.Semaphore(MAX_CONCURRENCY) # limits the concurrent requests to the endpoint

print(f"Loaded {len(PROXIES)} proxies | Max concurrency: {MAX_CONCURRENCY}")

# API endpoint to handle Google Lens requests
@app.get("/google-lens", response_class=HTMLResponse)
def google_lens(imageUrl: str = Query(..., description="Public image URL to search")):
    if not imageUrl.startswith("http"):
        raise HTTPException(status_code=400, detail="imageUrl must be a valid http/https URL")

    if not SEMAPHORE.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Too many concurrent requests. Try again shortly.")

    try:
        time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)) # request throttling delay to reduce bot detection risk
        html = exact_match_html(imageUrl, proxies=PROXIES)
        return HTMLResponse(content=html, status_code=200)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
    finally:
        SEMAPHORE.release()

# Run the app with: uvicorn server:app
if __name__ == "__main__":
    uvicorn.run("server_1:app", host="0.0.0.0", port=8000, workers=1)