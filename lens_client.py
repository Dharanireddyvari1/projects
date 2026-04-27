from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import TYPE_CHECKING, Mapping
from urllib.parse import parse_qs, urlencode, urlparse

if TYPE_CHECKING:
    import httpx


GOOGLE_ORIGIN = "https://www.google.com"
LENS_UPLOAD_URL = "https://lens.google.com/v3/upload"


class LensFlowError(RuntimeError):
    pass


@dataclass(frozen=True)
class LensSession:
    vsrid: tuple[str, ...]
    gsessionid: str
    lsessionid: str
    vsdim: str | None = None
    vsint: str | None = None


def browser_headers() -> dict[str, str]:
    return {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    }


def build_exact_match_url(session: LensSession) -> str:
    params: list[tuple[str, str]] = [
        ("udm", "48"),
        ("gsessionid", session.gsessionid),
        ("lsessionid", session.lsessionid),
        ("lns_surface", "26"),
        ("lns_mode", "un"),
        ("source", "lns.web.gsbubu"),
    ]

    for value in session.vsrid:
        params.append(("vsrid", value))

    if session.vsdim:
        params.append(("vsdim", session.vsdim))
    if session.vsint:
        params.append(("vsint", session.vsint))

    return f"{GOOGLE_ORIGIN}/search?{urlencode(params)}"


def parse_lens_session(search_url: str) -> LensSession:
    parsed = urlparse(search_url)
    query = parse_qs(parsed.query, keep_blank_values=True)

    missing = [key for key in ("vsrid", "gsessionid", "lsessionid") if not query.get(key)]
    if missing:
        raise LensFlowError(f"Lens redirect did not include required params: {', '.join(missing)}")

    return LensSession(
        vsrid=tuple(query["vsrid"]),
        gsessionid=query["gsessionid"][0],
        lsessionid=query["lsessionid"][0],
        vsdim=query.get("vsdim", [None])[0],
        vsint=query.get("vsint", [None])[0],
    )


def create_lens_session(client: "httpx.Client", image_url: str) -> LensSession:
    """Create a Lens session from an image URL using the Lens upload redirect.

    Chrome DevTools showed this chain:

    lens.google.com/v3/upload?url=...&ep=gsbubu...
      -> lens.google.com/v3/upload?url=... normalized
      -> google.com/search?...vsrid=...&gsessionid=...&lsessionid=...
    """
    upload_params = {
        "url": image_url,
        "ep": "gsbubu",
        "st": str(int(time() * 1000)),
        "hl": "en",
        "vpw": "1707",
        "vph": "295",
    }
    headers = {
        "referer": "https://www.google.com/",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-site",
        "sec-fetch-user": "?1",
    }

    next_url = f"{LENS_UPLOAD_URL}?{urlencode(upload_params)}"
    for _ in range(4):
        response = client.get(next_url, headers=headers, follow_redirects=False)
        if response.status_code not in (301, 302, 303, 307, 308):
            raise LensFlowError(
                f"Lens upload returned HTTP {response.status_code} without a redirect"
            )

        location = response.headers.get("location")
        if not location:
            raise LensFlowError("Lens upload redirect did not include a Location header")

        if location.startswith("/"):
            location = f"{GOOGLE_ORIGIN}{location}"

        parsed = urlparse(location)
        if parsed.netloc == "www.google.com" and parsed.path == "/search":
            return parse_lens_session(location)

        next_url = location

    raise LensFlowError("Lens upload redirect chain did not reach Google Search")


def looks_like_exact_match_html(html: str) -> bool:
    lowered = html.lower()
    return "searchresults" in lowered or "google search" in lowered


def is_anti_abuse_response(url: str, html: str) -> bool:
    lowered = html.lower()
    return "our systems have detected unusual traffic" in lowered or "/sorry/" in url


def fetch_exact_match_html_from_session(client: "httpx.Client", session: LensSession) -> str:
    exact_url = build_exact_match_url(session)
    response = client.get(exact_url)

    if response.status_code >= 400:
        raise LensFlowError(f"Google returned HTTP {response.status_code}")

    html = response.text
    if is_anti_abuse_response(str(response.url), html):
        raise LensFlowError("Google returned an anti-abuse interstitial instead of Exact Match HTML")

    if not looks_like_exact_match_html(html):
        raise LensFlowError("Response did not look like Google Exact Match HTML")

    return html


def fetch_exact_match_html(
    image_url: str,
    *,
    timeout: float = 45.0,
    proxy: str | None = None,
    extra_headers: Mapping[str, str] | None = None,
) -> str:
    try:
        import httpx
    except ImportError as exc:
        raise LensFlowError("Install dependencies first: pip install -r requirements.txt") from exc

    headers = browser_headers()
    if extra_headers:
        headers.update(extra_headers)

    client_kwargs = {
        "headers": headers,
        "timeout": timeout,
        "follow_redirects": True,
    }
    if proxy:
        client_kwargs["proxy"] = proxy

    with httpx.Client(**client_kwargs) as client:
        session = create_lens_session(client, image_url)
        return fetch_exact_match_html_from_session(client, session)
