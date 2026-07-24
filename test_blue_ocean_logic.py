from retailpool.scraper.blue_ocean_logic import analyze_blue_ocean, is_stm, calculate_concentration, estimate_sales_from_total_reviews
import json

def run_test():
    print("=== Testing STM Detector ===")
    print("Alga vs ИП AlgaTop:", is_stm("Alga", "ИП AlgaTop", 5)) # True
    print("Xiaomi vs WhiteStore:", is_stm("Xiaomi", "WhiteStore", 5)) # False
    print("Unknown vs Random (1 seller):", is_stm("Unknown", "Random", 1)) # True

    print("\n=== Testing Revenue Estimator ===")
    print("100 reviews -> Sales:", estimate_sales_from_total_reviews(100)) # 100/12 * 10 = 83

    print("\n=== Testing Niche Analyzer ===")
    mock_products = [
        # Lame Leader (High revenue, low rating)
        {
            "title": "Хреновое кресло",
            "price": 50000,
            "rating": 3.8,
            "review_count": 500, # Sales: 500/12 * 10 = ~416. Rev: 416 * 50k = 20M
            "brand": "BadChair",
            "buybox_seller": "ИП Мебельщик",
            "total_sellers": 5,
            "estimated_revenue": estimate_sales_from_total_reviews(500) * 50000
        },
        # STM Product (Brand == Seller)
        {
            "title": "Крутое кресло Alga",
            "price": 70000,
            "rating": 4.8,
            "review_count": 100,
            "brand": "Alga",
            "buybox_seller": "ИП AlgaTop",
            "total_sellers": 1,
            "estimated_revenue": estimate_sales_from_total_reviews(100) * 70000
        },
        # Monopolist Item
        {
            "title": "Обычное кресло",
            "price": 40000,
            "rating": 4.5,
            "review_count": 50,
            "brand": "NoName",
            "buybox_seller": "ИП Мебельщик", # Same seller as item 1
            "total_sellers": 3,
            "estimated_revenue": estimate_sales_from_total_reviews(50) * 40000
        }
    ]

    result = analyze_blue_ocean(mock_products)
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    run_test()
