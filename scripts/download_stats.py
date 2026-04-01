"""Quick script to check download counts across all releases."""
import json
import urllib.request

REPO = "harveyjenkins03-coder/valo-optimise"
URL = f"https://api.github.com/repos/{REPO}/releases"

try:
    req = urllib.request.Request(URL, headers={"User-Agent": "ValoOptimise"})
    data = json.loads(urllib.request.urlopen(req, timeout=10).read())

    total = 0
    for release in data:
        tag = release["tag_name"]
        for asset in release.get("assets", []):
            count = asset["download_count"]
            total += count
            print(f"  {tag}/{asset['name']}: {count}")

    print(f"\nTotal downloads: {total}")
except Exception as e:
    print(f"Error: {e}")
