__author__ = "Dharani Reddyvari"

import random
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

LENS_UPLOAD_URL = "https://lens.google.com/v3/upload"

BROWSER_PROFILES = [
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "platform": '"Windows"',
        "viewports": [(1366, 768), (1536, 864), (1707, 825), (1920, 1080)],
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Google Chrome";v="124", "Chromium";v="124", "Not.A/Brand";v="24"',
        "platform": '"Windows"',
        "viewports": [(1440, 900), (1600, 900), (1707, 825), (1920, 1080)],
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "sec_ch_ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "platform": '"macOS"',
        "viewports": [(1440, 900), (1512, 982), (1728, 1117)],
    },
]


def fetch_exact_match_html(image_url: str, proxy, headers: dict, width: int, height: int) -> str:
    
    upload_params = {
        "url": image_url,
        "ep": "gsbubu",
        "st": str(int(time.time() * 1000)),
        "hl": "en",
        "vpw": str(width),
        "vph": str(height),
    }

    timeout = httpx.Timeout(30.0, connect=15.0)
    with httpx.Client(headers=headers, proxy=proxy, timeout = timeout, http2=True,) as client:
        
        search_url = None
        redirect_url = f"{LENS_UPLOAD_URL}?{urlencode(upload_params)}"

        # Follow redirects until Google gives search URL
        for _ in range(5):
            response = client.get(redirect_url, follow_redirects=False)
            location = response.headers.get("location")

            if not location:
                raise RuntimeError(f"No redirect from Lens (status {response.status_code})")

            if location.startswith("/"):
                location = f"https://www.google.com{location}"

            parsed_location = urlparse(location)
            if parsed_location.netloc == "www.google.com" and parsed_location.path == "/search":
                search_url = location
                break

            redirect_url = location

        if not search_url:
            raise RuntimeError("Lens redirect chain did not reach Google Search")

        parsed_search = urlparse(search_url)
        query = parse_qs(parsed_search.query, keep_blank_values=True)

        missing = [k for k in ("vsrid", "gsessionid", "lsessionid") if not query.get(k)]
        if missing:
            raise RuntimeError(f"Search URL missing required params: {', '.join(missing)}")

        # udm=48 switches to the Exact Match tab
        query["udm"] = ["48"]
        exact_url = urlunparse(parsed_search._replace(query=urlencode(query, doseq=True)))

        time.sleep(random.uniform(0.6, 1.8))

        exact_response = client.get(exact_url, follow_redirects=True)
        exact_response.raise_for_status()

        html = exact_response.text
        lower_html = html.lower()

        if "/sorry/" in str(exact_response.url) or "unusual traffic" in lower_html or "captcha" in lower_html:
            raise RuntimeError("Hit Google anti-bot page")

        if "searchresultspage" not in lower_html and "<title>google search" not in lower_html:
            raise RuntimeError("Response did not look like Search result HTML")

        return html


def exact_match_html(image_url: str, proxies: list[str] | None = None) -> str:
    
    profile = random.choice(BROWSER_PROFILES)
    width, height = random.choice(profile["viewports"])
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "referer": "https://www.google.com/",
        "sec-ch-ua": profile["sec_ch_ua"],
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": profile["platform"],
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-site",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": profile["user_agent"],
    }

    # Try proxies in random order
    if proxies:
        proxy_attempts = list(proxies)
        random.shuffle(proxy_attempts)
    else:
        proxy_attempts = [None]

    failures = []
    retries_per_proxy = 2

    for proxy in proxy_attempts:
        for attempt in range(retries_per_proxy):
            try:
                if attempt > 0 or failures:
                    time.sleep(random.uniform(1.0, 3.0))
                return fetch_exact_match_html(image_url, proxy, headers, width, height)
            except (RuntimeError, httpx.HTTPError) as e:
                if attempt == retries_per_proxy - 1:
                    failures.append(f"{proxy or 'direct connection'} -> {e}")
                continue

    if failures:
        raise RuntimeError("All proxies failed: " + " | ".join(failures))

    raise RuntimeError("All retries exhausted")