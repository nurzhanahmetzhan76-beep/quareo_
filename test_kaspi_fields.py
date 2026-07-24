"""
Find all fields available in a single Kaspi product card from the internal API.
"""
import json

with open("kaspi_api_response.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for url, resp in data.items():
    if "cards" in (resp.get("data") or {}):
        cards = resp["data"]["cards"]
        # Print keys of first card
        if cards:
            first = cards[0]
            with open("kaspi_card_fields.txt", "w", encoding="utf-8") as out:
                out.write(f"Total cards: {len(cards)}\n\n")
                out.write("=== ALL KEYS IN FIRST CARD ===\n")
                for key, val in first.items():
                    if key == "previewImages":
                        out.write(f"  {key}: [{len(val)} images]\n")
                    elif isinstance(val, dict):
                        out.write(f"  {key}: {json.dumps(val, ensure_ascii=False)}\n")
                    else:
                        out.write(f"  {key}: {val}\n")
                
                out.write("\n=== SUMMARY OF ALL 20 CARDS ===\n")
                for card in cards:
                    out.write(f"  ID={card.get('id')} | brand={card.get('brand')} | price={card.get('unitPrice')} | rating={card.get('rating')} | reviews={card.get('reviewsQuantity')} | sellers={card.get('merchantsCount')} | title={str(card.get('title',''))[:50]}\n")
                
                # Check totalElements
                total = resp["data"].get("total", resp["data"].get("totalElements"))
                out.write(f"\ntotalElements/total: {total}\n")
            
            print("Done! See kaspi_card_fields.txt")
            break
