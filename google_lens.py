__author__ = "Dharani Reddyvari"

import random
import time
from collections.abc import Iterable
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


def get_exact_match_html(
    image_url: str,
    proxies: str | Iterable[str] | None = None,
    retries: int = 1,
    max_proxy_attempts: int = 5,
) -> str:
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

    if isinstance(proxies, str):
        proxy_pool = [proxies]
    elif proxies:
        proxy_pool = [proxy for proxy in proxies if proxy]
    else:
        proxy_pool = [None]

    random.shuffle(proxy_pool)
    proxy_pool = proxy_pool[:max_proxy_attempts]

    upload_params = {
        "url": image_url,
        "ep": "gsbubu",
        "st": str(int(time.time() * 1000)),
        "hl": "en",
        "vpw": str(width),
        "vph": str(height),
    }
    first_url = f"{LENS_UPLOAD_URL}?{urlencode(upload_params)}"
    failures = []

    for proxy in proxy_pool:
        for attempt in range(retries):
            try:
                if attempt > 0 or failures:
                    time.sleep(random.uniform(2, 5))

                print(f"Using proxy: {proxy or 'direct connection'}")

                timeout = httpx.Timeout(30.0, connect=15.0)
                with httpx.Client(headers=headers, proxy=proxy, timeout=timeout, http2=True) as client:
                    next_url = first_url
                    search_url = None

                    for _ in range(5):
                        response = client.get(next_url, follow_redirects=False)
                        location = response.headers.get("location")

                        if not location:
                            raise RuntimeError(f"No redirect from Lens (status {response.status_code})")

                        if location.startswith("/"):
                            location = f"https://www.google.com{location}"

                        parsed_location = urlparse(location)
                        if parsed_location.netloc == "www.google.com" and parsed_location.path == "/search":
                            search_url = location
                            break

                        next_url = location

                    if not search_url:
                        raise RuntimeError("Lens redirect chain did not reach Google Search")

                    parsed_search = urlparse(search_url)
                    query = parse_qs(parsed_search.query, keep_blank_values=True)

                    missing = [name for name in ("vsrid", "gsessionid", "lsessionid") if not query.get(name)]
                    if missing:
                        raise RuntimeError(f"Search URL missing required params: {', '.join(missing)}")

                    query["udm"] = ["48"]
                    exact_url = urlunparse(parsed_search._replace(query=urlencode(query, doseq=True)))

                    time.sleep(random.uniform(0.6, 1.8))
                    print(f"[attempt {attempt + 1}] fetching exact match: {exact_url}")

                    exact_response = client.get(exact_url, follow_redirects=True)
                    exact_response.raise_for_status()

                    html = exact_response.text
                    lower_html = html.lower()

                    if "/sorry/" in str(exact_response.url) or "unusual traffic" in lower_html or "captcha" in lower_html:
                        raise RuntimeError("Hit Google anti-bot page")

                    if "searchresultspage" not in lower_html and "<title>google search" not in lower_html:
                        raise RuntimeError("Google response did not look like Search result HTML")

                    return html

            except (
                RuntimeError,
                httpx.ConnectError,
                httpx.ProxyError,
                httpx.ReadError,
                httpx.RemoteProtocolError,
                httpx.TimeoutException,
                httpx.HTTPStatusError,
            ) as e:
                print(f"[attempt {attempt + 1}] failed with {proxy or 'direct connection'}: {e}")
                if attempt == retries - 1:
                    failures.append(f"{proxy or 'direct connection'} -> {e}")

    if failures:
        raise RuntimeError("All proxies failed: " + " | ".join(failures))

    raise RuntimeError("All retries exhausted")
