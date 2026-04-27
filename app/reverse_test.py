import httpx

url = "https://www.google.com/search?sca_esv=c28e6a7449b65c90&lns_surface=26&hl=en&sxsrf=ANbL-n4kBOP0TcswABUZtgzJbR0QtUbQNQ:1777269682555&udm=48&vsrid=CIWBqY-5sa_ezgEQAhgBIiRlMDE3NzEyMi0xNmQ3LTQ5ODYtYWI3OS05NmY2NjYyNGFiM2YyeiICZ2goDEJyCi5sZmUtZHVtbXk6YmZmYTE4YjktOGI3ZS00ZTI3LTg5YjUtNjc2N2M3MDM3MzljEkAKPi9ibnMvZ2gvYm9yZy9naC9ibnMvbGVucy1mcm9udGVuZC1hcGkvcHJvZC5sZW5zLWZyb250ZW5kLWFwaS8xOIny4MCtjZQD&vsint=CAIqDAoCCAcSAggKGAEgATojChYNAAAAPxUAAAA_HQAAgD8lAACAPzABEIAGGIAIJQAAgD8&lns_mode=un&source=lns.web.gsbubu&vsdim=768,1024&gsessionid=zbteflroSrdZQTwfN71OpmXY1qJryD82nvASP3sZ1QsYuCtFycw87A&lsessionid=rB0cwY_yWJBKNNw2WZMGYvZPjINONzSb0W29pomz4gq-N5v8BTw33Q&vsrid=CIWBqY-5sa_ezgEQAhgBIiRhODEyNzdlMC05YmRhLTQ3NTEtODg3My02N2Q5MzVlZjc4YWYyeiICZ2goDEJyCi5sZmUtZHVtbXk6YmZmYTE4YjktOGI3ZS00ZTI3LTg5YjUtNjc2N2M3MDM3MzljEkAKPi9ibnMvZ2gvYm9yZy9naC9ibnMvbGVucy1mcm9udGVuZC1hcGkvcHJvZC5sZW5zLWZyb250ZW5kLWFwaS8xOIny4MCtjZQDUAA&q=&sa=X&ved=2ahUKEwj26-TArY2UAxUe1fACHY-iH88Qs6gLegQIEBAB&biw=1707&bih=295&dpr=1.13"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

with httpx.Client(follow_redirects=True, timeout=30) as client:
    response = client.get(url, headers=headers)
html = response.text.lower()

checks = {
    "captcha": "captcha" in html,
    "sorry_block": "/sorry/" in str(response.url).lower() or "unusual traffic" in html,
    "exact_match_marker": "exact match" in html or "visually similar" in html,
    "html_size": len(response.text),
}

print(checks)
print("Status:", response.status_code)
print("Final URL:", response.url)
print("Length:", len(response.text))

with open("exact_match.html", "w", encoding="utf-8") as f:
    f.write(response.text)