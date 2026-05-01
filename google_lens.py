__author__ = "Dharani Reddyvari"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import random
import time
from collections.abc import Iterable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx  # async-capable HTTP client; used here in sync mode


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
LENS_UPLOAD_URL = "https://lens.google.com/v3/upload"  # Google Lens image-by-URL entry point

# ---------------------------------------------------------------------------
# Browser profiles
# Each profile mimics a specific real browser (Chrome on Windows/Mac).
# We randomize across profiles so each request looks like a different user.
# Each profile has: user-agent string, sec-ch-ua header, OS platform, and
# a list of realistic viewport sizes (width x height in pixels).
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Main scraping function
# ---------------------------------------------------------------------------
def get_exact_match_html(
    image_url: str,
    proxies: str | Iterable[str] | None = None,  # single proxy URL, list of proxies, or None for direct
    retries: int = 1,           # how many times to retry with the same proxy before moving to the next
    max_proxy_attempts: int = 5, # cap on how many proxies from the pool to try per request
) -> str:
    # Pick a random browser profile for this request
    profile = random.choice(BROWSER_PROFILES)
    width, height = random.choice(profile["viewports"])  # random realistic viewport

    # Build realistic browser request headers matching the chosen profile
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

    # ---------------------------------------------------------------------------
    # Build the proxy pool
    # Accept a single string, a list, or None; normalize to a list for uniform iteration
    # Shuffle so each request uses a different proxy order (natural load balancing)
    # Cap at max_proxy_attempts to avoid very long waits when many proxies are listed
    # ---------------------------------------------------------------------------
    if isinstance(proxies, str):
        proxy_pool = [proxies]
    elif proxies:
        proxy_pool = [proxy for proxy in proxies if proxy]
    else:
        proxy_pool = [None]  # None means connect directly without a proxy

    random.shuffle(proxy_pool)
    proxy_pool = proxy_pool[:max_proxy_attempts]

    # ---------------------------------------------------------------------------
    # Build the initial Google Lens upload URL
    # Google Lens works by submitting an image URL via query params.
    # ep=gsbubu is the endpoint tag for URL-based search.
    # st is a unix timestamp in milliseconds (prevents caching).
    # vpw/vph are the viewport size, which must match the browser profile.
    # ---------------------------------------------------------------------------
    upload_params = {
        "url": image_url,
        "ep": "gsbubu",
        "st": str(int(time.time() * 1000)),
        "hl": "en",
        "vpw": str(width),
        "vph": str(height),
    }
    first_url = f"{LENS_UPLOAD_URL}?{urlencode(upload_params)}"
    failures = []  # accumulates per-prox   y error messages for the final raised exception

    # ---------------------------------------------------------------------------
    # Outer loop: try each proxy in the shuffled pool
    # Inner loop: retry the same proxy N times before giving up on it
    # ---------------------------------------------------------------------------
    for proxy in proxy_pool:
        for attempt in range(retries):
            try:
                # Add a delay between retries or when switching proxies, to avoid rate limiting
                if attempt > 0 or failures:
                    time.sleep(random.uniform(2, 5))

                print(f"Using proxy: {proxy or 'direct connection'}")

                # 30s total timeout, 15s just for establishing the connection
                timeout = httpx.Timeout(30.0, connect=15.0)

                # http2=True makes requests look like real Chrome (which uses HTTP/2 by default)
                with httpx.Client(headers=headers, proxy=proxy, timeout=timeout, http2=True) as client:
                    next_url = first_url
                    search_url = None

                    # ---------------------------------------------------------------------------
                    # Follow the Lens redirect chain
                    # Google Lens responds with a series of redirects before landing on /search.
                    # We follow them manually (follow_redirects=False) so we can inspect each
                    # location header and stop when we reach www.google.com/search.
                    # ---------------------------------------------------------------------------
                    for _ in range(5):  # safety cap of 5 hops to prevent infinite loops
                        response = client.get(next_url, follow_redirects=False)
                        location = response.headers.get("location")

                        if not location:
                            raise RuntimeError(f"No redirect from Lens (status {response.status_code})")

                        # Relative URLs like /search?... need the host prepended
                        if location.startswith("/"):
                            location = f"https://www.google.com{location}"

                        parsed_location = urlparse(location)
                        if parsed_location.netloc == "www.google.com" and parsed_location.path == "/search":
                            search_url = location  # found our destination
                            break

                        next_url = location  # keep following the chain

                    if not search_url:
                        raise RuntimeError("Lens redirect chain did not reach Google Search")

                    # ---------------------------------------------------------------------------
                    # Validate required session params in the search URL
                    # Google Lens embeds session identifiers in the redirect URL.
                    # If they are missing, the search page will not return valid results.
                    # ---------------------------------------------------------------------------
                    parsed_search = urlparse(search_url)
                    query = parse_qs(parsed_search.query, keep_blank_values=True)

                    missing = [name for name in ("vsrid", "gsessionid", "lsessionid") if not query.get(name)]
                    if missing:
                        raise RuntimeError(f"Search URL missing required params: {', '.join(missing)}")

                    # ---------------------------------------------------------------------------
                    # Append udm=48 to switch to the Exact Match tab
                    # udm=48 is Google's internal filter for visually identical image results
                    # ---------------------------------------------------------------------------
                    query["udm"] = ["48"]
                    exact_url = urlunparse(parsed_search._replace(query=urlencode(query, doseq=True)))

                    # Small human-like delay before fetching the final page
                    time.sleep(random.uniform(0.6, 1.8))
                    print(f"[attempt {attempt + 1}] fetching exact match: {exact_url}")

                    exact_response = client.get(exact_url, follow_redirects=True)
                    exact_response.raise_for_status()  # raises on 4xx / 5xx HTTP errors

                    html = exact_response.text
                    lower_html = html.lower()

                    # ---------------------------------------------------------------------------
                    # Bot detection checks
                    # Google redirects to /sorry/ or shows a CAPTCHA page when it detects automation.
                    # We check the URL and the page content for known signals.
                    # ---------------------------------------------------------------------------
                    if "/sorry/" in str(exact_response.url) or "unusual traffic" in lower_html or "captcha" in lower_html:
                        raise RuntimeError("Hit Google anti-bot page")

                    # Sanity check that the page actually looks like Google Search results
                    if "searchresultspage" not in lower_html and "<title>google search" not in lower_html:
                        raise RuntimeError("Google response did not look like Search result HTML")

                    return html  # success — return the raw HTML to the caller

            except (
                RuntimeError,          # our own raised errors (bot block, bad redirect, etc.)
                httpx.ConnectError,    # could not connect to the proxy or target
                httpx.ProxyError,      # proxy returned an error (e.g. 407 auth failure)
                httpx.ReadError,       # connection was closed mid-response (WinError 10054)
                httpx.RemoteProtocolError,  # unexpected HTTP protocol response
                httpx.TimeoutException,    # request took too long
                httpx.HTTPStatusError,     # raise_for_status() triggered (4xx/5xx)
            ) as e:
                print(f"[attempt {attempt + 1}] failed with {proxy or 'direct connection'}: {e}")
                if attempt == retries - 1:
                    # All retries for this proxy exhausted — record it and move to the next proxy
                    failures.append(f"{proxy or 'direct connection'} -> {e}")

    # Every proxy in the pool failed — surface all errors in one message
    if failures:
        raise RuntimeError("All proxies failed: " + " | ".join(failures))

    raise RuntimeError("All retries exhausted")  # safety fallback (should not normally be reached)
