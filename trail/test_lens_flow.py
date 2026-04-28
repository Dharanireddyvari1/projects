import argparse
from pathlib import Path

from lens_client import LensFlowError, fetch_exact_match_html


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Google Lens Exact Match HTML for one image URL.")
    parser.add_argument("image_url")
    parser.add_argument("--out", type=Path, default=Path("exact_match_live.html"))
    args = parser.parse_args()

    try:
        html = fetch_exact_match_html(args.image_url)
    except LensFlowError as exc:
        raise SystemExit(f"Lens flow failed: {exc}") from exc

    args.out.write_text(html, encoding="utf-8")
    print(f"Wrote {len(html):,} characters to {args.out}")


if __name__ == "__main__":
    main()
