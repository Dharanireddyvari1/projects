import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse


INTERESTING_TERMS = (
    "batchexecute",
    "uploadbyurl",
    "lens",
    "visualsearch",
    "gsbubu",
    "search",
    "vsrid",
    "gsessionid",
    "lsessionid",
    "udm=48",
)

SESSION_KEYS = {
    "vsrid",
    "gsessionid",
    "lsessionid",
    "lns_surface",
    "lns_mode",
    "source",
    "udm",
    "vsdim",
    "vsint",
}


@dataclass
class Candidate:
    index: int
    method: str
    url: str
    status: int | None
    mime_type: str
    score: int
    reasons: list[str]
    query_params: dict[str, list[str]]
    post_preview: str
    response_preview: str


def _collect_params(url: str) -> dict[str, list[str]]:
    parsed = urlparse(url)
    params: dict[str, list[str]] = {}
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        params.setdefault(key, []).append(value)
    return params


def _post_text(request: dict[str, Any]) -> str:
    post_data = request.get("postData") or {}
    text = post_data.get("text") or ""
    if text:
        return text

    params = post_data.get("params") or []
    if params:
        return "&".join(f"{p.get('name', '')}={p.get('value', '')}" for p in params)

    return ""


def _response_text(response: dict[str, Any]) -> str:
    content = response.get("content") or {}
    return content.get("text") or ""


def _preview(value: str, limit: int = 700) -> str:
    cleaned = value.replace("\r", "\\r").replace("\n", "\\n")
    return cleaned[:limit]


def find_candidates(har: dict[str, Any]) -> list[Candidate]:
    entries = har.get("log", {}).get("entries", [])
    candidates: list[Candidate] = []

    for index, entry in enumerate(entries):
        request = entry.get("request") or {}
        response = entry.get("response") or {}
        method = request.get("method", "")
        url = request.get("url", "")
        status = response.get("status")
        mime_type = (response.get("content") or {}).get("mimeType", "")
        post_text = _post_text(request)
        response_text = _response_text(response)

        haystack = " ".join((url, post_text, response_text[:3000])).lower()
        reasons = [term for term in INTERESTING_TERMS if term.lower() in haystack]

        params = _collect_params(url)
        session_hits = sorted(set(params) & SESSION_KEYS)
        reasons.extend(f"query:{key}" for key in session_hits)

        score = len(reasons)
        if urlparse(url).netloc.endswith("google.com"):
            score += 1
        if "batchexecute" in url.lower():
            score += 5
        if "udm" in params and "48" in params["udm"]:
            score += 6
        if "vsrid" in params:
            score += 4
        if "lens" in url.lower():
            score += 3
        if method.upper() == "POST":
            score += 1

        if score:
            candidates.append(
                Candidate(
                    index=index,
                    method=method,
                    url=url,
                    status=status,
                    mime_type=mime_type,
                    score=score,
                    reasons=reasons,
                    query_params={key: params[key] for key in params if key in SESSION_KEYS},
                    post_preview=_preview(post_text),
                    response_preview=_preview(response_text),
                )
            )

    return sorted(candidates, key=lambda item: item.score, reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find likely Google Lens bootstrap/session requests in a Chrome DevTools HAR export."
    )
    parser.add_argument("har_path", type=Path)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument(
        "--show-response",
        action="store_true",
        help="Print response previews. Useful if the HAR includes response bodies.",
    )
    args = parser.parse_args()

    har = json.loads(args.har_path.read_text(encoding="utf-8"))
    candidates = find_candidates(har)

    for candidate in candidates[: args.limit]:
        print("=" * 100)
        print(f"#{candidate.index} score={candidate.score} {candidate.method} status={candidate.status}")
        print(candidate.url)
        print(f"mime: {candidate.mime_type}")
        print(f"reasons: {', '.join(candidate.reasons)}")
        if candidate.query_params:
            print("session/query params:")
            for key, values in candidate.query_params.items():
                print(f"  {key}: {values}")
        if candidate.post_preview:
            print(f"post preview: {candidate.post_preview}")
        if args.show_response and candidate.response_preview:
            print(f"response preview: {candidate.response_preview}")


if __name__ == "__main__":
    main()
