__author__ = "Dharani Reddyvari"

import random
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

# Rotate these so we don't look like a bot hammering with the same UA
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]


def build_headers(ua: str) -> dict:
    return {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "referer": "https://www.google.com/",
        "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-site",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": ua,
    }


def get_exact_match_html(image_url: str, proxy: str = None, retries: int = 3) -> str:
    ua = random.choice(USER_AGENTS) # rotate user agent for each request to avoid looking like a bot
    headers = build_headers(ua) # build headers with the chosen user agent : Realistic browser headers

    proxies = {"http://": proxy, "https://": proxy} if proxy else None

    upload_url = "https://lens.google.com/v3/upload"
    upload_params = {
        "url": image_url,
        "ep": "gsbubu",
        "st": str(int(time.time() * 1000)),
        "hl": "en",
        "vpw": "1707",
        "vph": "825",
    }

    for attempt in range(retries):
        try:
            # small random delay so we don't hammer google on retries
            if attempt > 0:
                time.sleep(random.uniform(2, 5))

            with httpx.Client(headers=headers, proxies=proxies, timeout=45) as client: # Cookie/session reuse, realistic headers, and proxy support for better reliability

                resp = client.get(
                    f"{upload_url}?{urlencode(upload_params)}",
                    follow_redirects=False,
                )

                location = resp.headers.get("location")
                if not location:
                    raise RuntimeError(f"No redirect from Lens (status {resp.status_code})")

                if location.startswith("/"):
                    location = f"https://www.google.com{location}"

                parsed = urlparse(location)
                if parsed.netloc != "www.google.com" or parsed.path != "/search":
                    raise RuntimeError(f"Unexpected redirect target: {location}")

                # append udm=48 to land on the Exact Match tab
                query = parse_qs(parsed.query, keep_blank_values=True)
                query["udm"] = ["48"]
                exact_url = urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

                print(f"[attempt {attempt + 1}] fetching exact match: {exact_url}")

                exact_resp = client.get(exact_url, follow_redirects=True)
                exact_resp.raise_for_status()

                html = exact_resp.text

                # if google blocked us we get a /sorry/ redirect or captcha page
                if "/sorry/" in str(exact_resp.url) or "unusual traffic" in html.lower():
                    raise RuntimeError("Hit Google anti-bot page")

                return html

        except RuntimeError as e:
            print(f"[attempt {attempt + 1}] failed: {e}")
            if attempt == retries - 1:
                raise

    raise RuntimeError("All retries exhausted")