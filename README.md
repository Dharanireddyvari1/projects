# Google Lens Exact Match API

This project builds a small FastAPI service that accepts an image URL, runs a reverse-engineered Google Lens flow, and returns the raw HTML from the Exact Match results page.

## Approach

The final Exact Match URL copied from the browser is not reusable because it contains short-lived session values such as `vsrid`, `gsessionid`, and `lsessionid`.

Instead, this API creates a fresh Lens session for every request:

```text
imageUrl
-> https://lens.google.com/v3/upload
-> Google redirects to /search with fresh Lens session parameters
-> the script changes udm to 48 for Exact Match
-> the API returns the resulting HTML
```

The main scraping logic is in `google_lens_1.py`. The API server is in `server_1.py`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Environment

Create a `.env` file in the project folder. Do not commit this file because it contains proxy credentials.

Example:

```env
PROXY_LIST=http://user:pass@host:port,http://user:pass@host2:port
MAX_CONCURRENCY=5
REQUEST_DELAY_MIN=0.2
REQUEST_DELAY_MAX=1.0
```

For Oxylabs Datacenter Proxies, use the proxy username, password, host, and port format shown in the Oxylabs dashboard.

## Run Locally

```powershell
python server_1.py
```

The API runs on:

```text
http://localhost:8000
```

## API Endpoint

```text
GET /google-lens?imageUrl={image_url}
```

Example:

```powershell
curl.exe "http://127.0.0.1:8000/google-lens?imageUrl=https%3A%2F%2Fi.ebayimg.com%2Fimages%2Fg%2FbRoAAeSwDgxp5kQn%2Fs-l1600.webp" -o exact_match.html
```

The response body is the raw HTML from the Exact Match results page.

## Anti-Bot Handling

The implementation includes:

- Browser-like request headers.
- Rotating browser profiles with matching User-Agent, client hints, platform, and viewport.
- Proxy rotation through `PROXY_LIST`.
- One `httpx.Client` per image flow so cookies stay consistent.
- Random delays between requests and retries.
- A server-side concurrency limit using `MAX_CONCURRENCY`.
- Basic detection for Google `/sorry/`, unusual traffic, and CAPTCHA pages.

## Hosting

To expose the local API for testing:

```powershell
ngrok http 8000
```

Share the generated ngrok URL and the configured `MAX_CONCURRENCY` value.

## Notes

- The API does not store or reuse copied Google Exact Match URLs.
- Each request generates a new Lens session from the provided image URL.
- Free or trial proxies may fail sometimes, so proxy retries are expected.
