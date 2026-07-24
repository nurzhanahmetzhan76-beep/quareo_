import re
from typing import List, Dict, Any
from collections import Counter

def normalize_name(name: str) -> str:
    """Removes standard prefixes/suffixes and makes lowercase for accurate comparison."""
    if not name:
        return ""
    name = name.lower()
    # Remove IP, TOO, LLC, etc.
    name = re.sub(r'\b(ип|тоо|ooo|зао|llc|ltd|inc|магазин|shop|store)\b', '', name)
    # Remove punctuation
    name = re.sub(r'[^\w\s]', '', name)
    return name.strip()

def is_stm(brand: str, seller_name: str, total_sellers: int) -> bool:
    """
    Detects if a product is Private Label (STM).
    Returns True ONLY if the brand name matches the seller name.
    """
    norm_brand = normalize_name(brand)
    norm_seller = normalize_name(seller_name)
    
    # Generic brands are never considered STM
    if norm_brand in ["безбренда", "unknown", "generic", ""]:
        return False
        
    # Check for substring match (true STM)
    if norm_brand and norm_seller:
        if len(norm_brand) > 2 and norm_brand in norm_seller:
            return True
        if len(norm_seller) > 2 and norm_seller in norm_brand:
            return True
            
    return False

def calculate_review_velocity(reviews_last_30_days: int, conversion_rate: float = 0.10) -> int:
    """
    Estimates sales based on the number of reviews in the last 30 days.
    Formula: Reviews * (1 / Conversion Rate)
    """
    multiplier = 1 / conversion_rate
    return int(reviews_last_30_days * multiplier)

def estimate_sales_from_total_reviews(total_reviews: int, active_months: int = 12, conversion_rate: float = 0.10) -> int:
    """
    Fallback method: If we can't scrape exact 30-day reviews, we estimate monthly average.
    """
    if active_months <= 0:
        active_months = 1
    monthly_reviews = total_reviews / active_months
    return calculate_review_velocity(monthly_reviews, conversion_rate)

def calculate_concentration(buybox_sellers: List[str]) -> Dict[str, Any]:
    """
    Calculates the monopoly / concentration index based on Top 30 items.
    Returns the share of the top 3 sellers.
    """
    if not buybox_sellers:
        return {"top_3_share": 0.0, "is_oligopoly": False, "unique_sellers": 0}
        
    counts = Counter(buybox_sellers)
    total_items = len(buybox_sellers)
    
    # Sort sellers by frequency
    top_sellers = counts.most_common(3)
    top_3_items = sum(count for _, count in top_sellers)
    
    top_3_share = top_3_items / total_items
    
    return {
        "top_3_share": top_3_share,
        "is_oligopoly": top_3_share >= 0.50, # If 1-3 sellers hold > 50%
        "unique_sellers": len(counts),
        "top_sellers": top_sellers
    }

def is_lame_leader(revenue: float, rating: float, revenue_threshold: float = 3000000.0, max_rating: float = 4.49) -> bool:
    """
    Detects a 'Lame Leader': High sales but poor quality/service.
    """
    if rating is None:
        return False
    return revenue >= revenue_threshold and rating <= max_rating

def analyze_blue_ocean(products: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregates metrics for the entire niche (Top 30 products).
    Expected product dict keys:
    - title, price, brand, buybox_seller, total_sellers, rating, estimated_revenue
    """
    total_items = len(products)
    if total_items == 0:
        return {}

    stm_count = 0
    lame_leaders = []
    buybox_sellers = []
    
    total_revenue = 0
    
    for prod in products:
        brand = prod.get("brand", "")
        seller = prod.get("buybox_seller", "")
        sellers_cnt = prod.get("total_sellers", 1)
        revenue = prod.get("estimated_revenue", 0)
        rating = prod.get("rating", 5.0)
        
        # 1. STM Check
        if is_stm(brand, seller, sellers_cnt):
            stm_count += 1
            prod["is_stm"] = True
        else:
            prod["is_stm"] = False
            
        # 2. BuyBox tracking for concentration
        if seller:
            buybox_sellers.append(seller)
            
        # 3. Lame Leaders
        if is_lame_leader(revenue, rating):
            lame_leaders.append(prod)
            prod["is_lame_leader"] = True
        else:
            prod["is_lame_leader"] = False
            
        total_revenue += revenue
            
    # Niche Metrics
    stm_share = stm_count / total_items
    concentration_data = calculate_concentration(buybox_sellers)
    
    is_stm_red_ocean = stm_share > 0.45
    is_oligopoly = concentration_data.get("is_oligopoly", False)
    
    # Verdict
    is_red_ocean = is_stm_red_ocean or is_oligopoly
    
    return {
        "scanned_items": total_items,
        "total_niche_revenue": total_revenue,
        "stm_share": stm_share,
        "is_stm_red_ocean": is_stm_red_ocean,
        "concentration": concentration_data,
        "is_oligopoly_red_ocean": is_oligopoly,
        "is_red_ocean": is_red_ocean,
        "lame_leaders": lame_leaders,
        "lame_leaders_count": len(lame_leaders)
    }
