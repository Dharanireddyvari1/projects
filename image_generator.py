import csv

with open("input_urls.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["imageUrl"])

    for i in range(1, 1001):
        writer.writerow([f"https://picsum.photos/id/{i}/500/500"])