__author__ = "Dharani Reddyvari"

from time import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
import httpx

class GoogleLensExactMatch:


    def __init__(self):

        self.headers = {
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
            "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/125.0.0.0 Safari/537.36")
        }


    def get_exact_match_html(self, image_url: str) -> str:

        upload_url = "https://lens.google.com/v3/upload"
        upload_params = {
            "url": image_url,
            "ep": "gsbubu",
            "st": str(int(time() * 1000)),
            "hl": "en",
            "vpw": "1707",
            "vph": "825",
        }
        params_encoded = urlencode(upload_params)

        with httpx.Client(headers=self.headers,timeout = 45) as client:
            final_upload_url = f"{upload_url}?{params_encoded}"
            search_url = None

            for _ in range(5):
                response = client.get(final_upload_url, follow_redirects=False)
                location = response.headers.get("location")

                if not location:
                    raise RuntimeError(f"Google Lens did not return a redirect. Status: {response.status_code}")
                
                if location.startswith("/"):
                    location = f"https://www.google.com{location}"

                parsed_location = urlparse(location)
                if parsed_location.netloc == "www.google.com" and parsed_location.path == "/search":
                    search_url = location
                    break
            print("Search URL:", search_url)
            
            if not search_url:
                raise RuntimeError("Google Lens did not return a valid search URL.")
            
            parsed_search = urlparse(search_url)
            query = parse_qs(parsed_search.query, keep_blank_values=True)

            required_params = ["vsrid", "gsessionid", "lsessionid"]
            missing_params = [param for param in required_params if param not in query]
            if missing_params:
                raise RuntimeError(f"Generated Search URL is missing: {', '.join(missing_params)}")

            query["udm"] = ["48"]
            exact_match_url = urlunparse(
                parsed_search._replace(query=urlencode(query, doseq=True))
            )

            exact_response = client.get(exact_match_url, follow_redirects=True)
            exact_response.raise_for_status()

            html = exact_response.text
            if "our systems have detected unusual traffic" in html.lower() or "/sorry/" in str(exact_response.url):
                raise RuntimeError("Google returned an anti-bot page instead of Exact Match HTML.")

            return html