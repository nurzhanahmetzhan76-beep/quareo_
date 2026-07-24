"""
Dump contents of Kaspi offer-view and review-view API responses.
"""
import json

with open("kaspi_product_api.json", "r", encoding="utf-8") as f:
    data = json.load(f)

with open("kaspi_api_structure.txt", "w", encoding="utf-8") as out:
    for url, resp in data.items():
        if "offer-view" in url or "review-view" in url:
            out.write(f"\n{'='*80}\n")
            out.write(f"URL: {url}\n")
            out.write(f"{'='*80}\n")
            out.write(json.dumps(resp, ensure_ascii=False, indent=2)[:3000])
            out.write("\n...\n")
