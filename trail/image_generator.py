import csv
from urllib.parse import urlparse, urlunparse

with open("input_urls.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["imageUrl"])

    for i in range(1, 1001):
        writer.writerow([f"https://picsum.photos/id/{i}/500/500"])

location = "https://www.google.com/search?vsrid=CLyE6cfZyf_dkgEQAhgBIiRhOTY4YzE5OC1iMmNkLTQ4MDUtYmQyOS1jNDYyMjg0YzIwYTgyeyICYmkoBkJzCi5sZmUtZHVtbXk6MGFiMTBkN2MtY2ZhZS00NmQyLWE1Y2ItMDUzNjc4NWEwY2FlEkEKPy9ibnMvYmkvYm9yZy9iaS9ibnMvbGVucy1mcm9udGVuZC1hcGkvcHJvZC5sZW5zLWZyb250ZW5kLWFwaS8zNDi-wLuR_ZeUAw&vsint=CAIqDAoCCAcSAggKGAEgATojChYNAAAAPxUAAAA_HQAAgD8lAACAPzABEIAGGIAIJQAAgD8&udm=26&lns_mode=un&source=lns.web.gsbubu&vsdim=768,1024&gsessionid=vXBVgDp09pV19smSERlhQKp5wk_EWJhnvYoaN9evHkP01MS6dJ0eMg&lsessionid=Ov8dZC5uxnsr9ToSCQdawhBEwLinNK5gtVHDcrPmhyOa3aTUV_TWQg&lns_surface=26&lns_vfs=e&qsubts=1777634652662&biw=1707&bih=825&hl=en"
print(urlparse(location))
