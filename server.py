__author__ = "Dharani Reddyvari"

import os
import random

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from google_lens import get_exact_match_html

app = FastAPI(title="Google Lens Exact Match API")

# drop your proxy list here, one per line e.g. "http://user:pass@host:port"
# or set PROXY_LIST env var as a comma-separated string
RAW_PROXIES = os.getenv("PROXY_LIST", "") 
PROXIES = [p.strip() for p in RAW_PROXIES.split(",") if p.strip()]
print(f"Loaded {len(PROXIES)} proxies")


@app.get("/google-lens", response_class=HTMLResponse)
async def google_lens(imageUrl: str = Query(..., description="Public image URL to search")):
    if not imageUrl.startswith("http"):
        raise HTTPException(status_code=400, detail="imageUrl must be a valid http/https URL")

    proxy = random.choice(PROXIES) if PROXIES else None

    try:
        html = get_exact_match_html(imageUrl, proxy=proxy)
        return HTMLResponse(content=html, status_code=200)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, workers=4)