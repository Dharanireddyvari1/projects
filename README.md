# Google Lens Exact Match API

Reverse-engineers the Google Lens upload flow to return Exact Match result HTML — no browser required.

## Approach

Instead of launching a browser, the API hits `lens.google.com/v3/upload` directly with the image URL as a query param. Google redirects to `google.com/search` with session tokens (`vsrid`, `gsessionid`, etc.). We append `udm=48` to that URL which switches to the Exact Match tab, then return the HTML.

This is faster and more stable than browser automation because there's no Chromium overhead.

## Setup

```bash
pip install httpx fastapi uvicorn
```

## Run locally

```bash
python server.py
```

API will be at `http://localhost:8000`.

## With proxies

Set a comma-separated proxy list before starting:

```bash
export PROXY_LIST="http://user:pass@host1:port,http://user:pass@host2:port"
python server.py
```

## Example call

```
GET http://localhost:8000/google-lens?imageUrl=https://i.ebayimg.com/00/s/MTYwMFgxNjAw/z/BVcAAOSwS9m4zOb/$_57.JPG
```

Response: raw HTML string of the Exact Match results page.

## Expose via ngrok

```bash
ngrok http 8000
```

## Anti-bot strategy

- Rotates User-Agent strings across common Chrome/Firefox versions
- Random delays between retries (2–5s)
- Proxy rotation via `PROXY_LIST` env var
- Detects `/sorry/` redirects and CAPTCHA pages, retries on those

## Max concurrency

Depends on proxy pool size and server resources. With `workers=4` in uvicorn and a decent proxy list, ~10–20 concurrent requests is reasonable.