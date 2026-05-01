# Google Lens Exact Match API

A FastAPI service that takes an image URL, runs it through Google Lens, and hands back the raw HTML from the Exact Match search page.

## Why This Exists

If you've ever tried copying a Lens URL from your browser and reusing it, you know it stops working almost immediately. The URL contains temporary session values (`vsrid`, `gsessionid`, `lsessionid`) that expire fast. This service works around that by spinning up a fresh Lens session for every single request instead of trying to reuse stale ones.

The flow looks like this:

`image URL → lens.google.com/v3/upload → follow redirects → get /search URL → switch to udm=48 (Exact Match) → return HTML `

## Project Files

- `server_1.py` — the FastAPI server
- `google_lens_1.py` — the Lens scraping logic
- `run_csv_load_test.ps1` — optional load test script for batch testing locally

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a `.env` file in the project root with your config (don't commit this):

```env
PROXY_LIST=http://user:pass@host:port,http://user:pass@host2:port
MAX_CONCURRENCY=5
REQUEST_DELAY_MIN=0.5
REQUEST_DELAY_MAX=2.0
```

**`PROXY_LIST`** — comma-separated proxy URLs. Oxylabs Datacenter proxies work well here; use the exact credentials/host/port from your dashboard.  
**`MAX_CONCURRENCY`** — how many requests can run in parallel before the semaphore starts blocking.  
**`REQUEST_DELAY_MIN` / `REQUEST_DELAY_MAX`** — random delay range (in seconds) injected before each scrape attempt.

## Running It

```powershell
python -m server_1
```

- Local base URL: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

## API

`GET /google-lens?imageUrl={public_image_url}`

**Local:**
```powershell
curl.exe "http://127.0.0.1:8000/google-lens?imageUrl=https%3A%2F%2Fi.ebayimg.com%2Fimages%2Fg%2FbRoAAeSwDgxp5kQn%2Fs-l1600" -o exact_match.html
```

**Hosted on Render:**
```powershell
curl.exe "https://projects-54k7.onrender.com/google-lens?imageUrl=https%3A%2F%2Fi.ebayimg.com%2Fimages%2Fg%2FbRoAAeSwDgxp5kQn%2Fs-l1600" -o exact_match.html
```

A `200` gives you back raw HTML (`text/html`). Other status codes you might see:

| Code | Meaning |
|------|---------|
| `400` | Bad `imageUrl` |
| `429` | Too many concurrent requests |
| `502` | Proxy/Lens/Google blocked or redirect failed |
| `500` | Something unexpected went wrong |

## Testing

**Quick sanity check** — just open this in your browser or Postman while the server is running:

`http://127.0.0.1:8000/google-lens?imageUrl=https%3A%2F%2Fi.ebayimg com%2Fimages%2Fg%2FbRoAAeSwDgxp5kQn%2Fs-l1600`

You should get a `200` with `text/html` content.

**Batch test from a CSV:**
```powershell
.\run_csv_load_test.ps1 -CsvPath .\urls_10.csv -SaveHtml -OutputDir .\results
```

This saves per-request HTML files into `results/` and dumps summary + detail CSVs.

## How Anti-Bot Works

Google will block you if you're not careful. A few things this service does to stay under the radar:

- Browser-realistic headers and client hints
- Rotating user agents, platforms, and viewport sizes
- Proxy rotation with retries across the full `PROXY_LIST`
- One `httpx.Client` per request to preserve cookie/session state across the redirect chain
- Manual redirect walking (not auto-follow) so we can capture the session params we need
- Random delays between requests
- Concurrency limiting via semaphore
- Basic detection for Google's block pages (`/sorry/`, CAPTCHA markers, "unusual traffic" pages)

Proxy quality makes a big difference here. Cheap proxies will get blocked faster and tank your success rate.

## Deployment

Hosted on Render at `https://projects-54k7.onrender.com`. The public endpoint is:

`https://projects-54k7.onrender.com/google-lens`

Concurrency on the hosted instance is controlled by `MAX_CONCURRENCY` in the environment config.