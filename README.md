# Google Lens Exact Match API

Reverse-engineered API for returning raw Google Lens Exact Match HTML from an image URL.

## Approach

The API does not reuse copied Exact Match URLs because those URLs expire quickly. Instead, each request creates a fresh Lens session:

```text
imageUrl
-> lens.google.com/v3/upload
-> Google Search redirect with vsrid, gsessionid, lsessionid
-> switch udm to 48 for Exact Match
-> fetch and return raw HTML
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Environment

Create a local `.env` file. Do not commit it.

```env
PROXY_LIST=http://user:pass@host:port,http://user:pass@host2:port
MAX_CONCURRENCY=5
REQUEST_DELAY_MIN=0.2
REQUEST_DELAY_MAX=1.0
```

For Oxylabs Datacenter Proxies, use the proxy entrypoint and authenticated username/password format shown by the Oxylabs dashboard.

## Run Locally

```powershell
python server.py
```

The API will run at:

```text
http://localhost:8000
```

## Endpoints

Health check:

```text
GET /health
```

Proxy check:

```text
GET /proxy-health
```

Google Lens Exact Match:

```text
GET /google-lens?imageUrl=https://example.com/image.jpg
```

The response body is the raw Exact Match HTML.

## Anti-Bot Strategy

- Uses a persistent `httpx.Client` per image flow so cookies are preserved.
- Rotates consistent browser profiles: User-Agent, client hints, platform, and viewport.
- Rotates through the configured proxy pool and fails over when a proxy is unavailable.
- Uses random request delays and a server-side concurrency limit.
- Detects Google `/sorry/`, unusual-traffic, and CAPTCHA responses.
- Manually follows the Lens redirect chain to generate fresh session parameters.

## Expose With Ngrok

```powershell
ngrok http 8000
```

Share the generated public URL and the configured `MAX_CONCURRENCY` value.
