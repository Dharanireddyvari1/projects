# Google Lens Exact Match API

Work-in-progress solution for the MrScraper coding challenge.

Goal:

```http
GET /google-lens?imageUrl={image_url}
```

The API should return the raw HTML from the Google Lens **Exact match** results page.

## Current Approach

We are pursuing the higher-scoring reverse-engineering path instead of relying only on full browser automation.

Observed so far:

- The final Exact Match URL is a Google `/search?udm=48...` URL.
- It does not contain the original image URL.
- It contains generated, short-lived, session-bound values such as:
  - `vsrid`
  - `gsessionid`
  - `lsessionid`
  - `vsdim`
  - `vsint`
- Reusing a captured Exact Match URL works briefly, but it expires and is not a complete solution.

The next task is to identify the earlier Google Lens request that creates those session values from the submitted image URL.

## Analyze Chrome DevTools HAR

1. Open Chrome DevTools.
2. Go to the **Network** tab.
3. Enable **Preserve log**.
4. Manually run the Google Lens flow:
   - submit an image URL
   - wait for results
   - click **Exact match**
5. Right-click the Network table.
6. Choose **Save all as HAR with content**.
7. Run:

```powershell
python har_analyzer.py path\to\lens-flow.har --show-response
```

Interesting requests usually contain one or more of:

- `batchexecute`
- `uploadbyurl`
- `lens`
- `visualsearch`
- `gsbubu`
- `search`
- `vsrid`
- `gsessionid`
- `lsessionid`
- `udm=48`

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If Python/httpx fails with an SSL key logging permission error, remove the inherited environment variable:

```powershell
Remove-Item Env:SSLKEYLOGFILE
```

## Files

- `har_analyzer.py` ranks likely Google Lens bootstrap/session requests from a HAR export.
- `lens_client.py` contains the direct-flow skeleton.
- `test_lens_flow.py` runs the reverse-engineered flow for one image URL and saves the HTML.
- `requirements.txt` contains Python dependencies.

## Test The Direct Flow

```powershell
python test_lens_flow.py "https://i.ebayimg.com/images/g/apsAAeSw1URp7CAK/s-l1600.webp"
```

Expected output:

```text
Wrote 200,000+ characters to exact_match_live.html
```

If the request fails with a Google anti-abuse page, retry with a proxy or a fresh browser-like session.
