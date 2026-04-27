from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping
from urllib.parse import urlencode

if TYPE_CHECKING:
    import httpx


GOOGLE_ORIGIN = "https://www.google.com"


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


def create_lens_session(client: "httpx.Client", image_url: str) -> LensSession:
    """Create a Lens session from an image URL.

    This is the reverse-engineering boundary. After har_analyzer.py identifies
    the POST/GET that returns vsrid, gsessionid, and lsessionid, implement that
    request here and parse its response.
    """
    raise NotImplementedError(
        "Export a Chrome DevTools HAR from a successful Lens flow, then use "
        "har_analyzer.py to identify the request that creates the Lens session."
    )


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
        exact_url = build_exact_match_url(session)
        response = client.get(exact_url)

    if response.status_code >= 400:
        raise LensFlowError(f"Google returned HTTP {response.status_code}")

    html = response.text
    lowered = html.lower()
    if "our systems have detected unusual traffic" in lowered or "/sorry/" in str(response.url):
        raise LensFlowError("Google returned an anti-abuse interstitial instead of Exact Match HTML")

    if "google" not in lowered:
        raise LensFlowError("Response did not look like Google HTML")

    return html
