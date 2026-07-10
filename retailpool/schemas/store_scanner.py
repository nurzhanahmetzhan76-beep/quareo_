from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class ProductAnalytics(BaseModel):
    sku: str
    name: str
    price: int
    sold_count: int
    revenue: int
    purchase_cost: int
    commission: int
    profit: int
    roi_percent: float
    category: str = Field(..., description="A, B, or C for ABC analysis")
    ai_advice: str

class MonthlyData(BaseModel):
    month: str
    revenue: int
    profit: int

class SeasonalTrend(BaseModel):
    season: str
    top_product_name: str
    peak_month: str
    sales_volume: int
    ai_advice: str

class StoreScanRequest(BaseModel):
    target: str = Field(..., description="Phone number, store ID, or Kaspi Seller API Key")
    scan_type: str = Field(..., description="guest or deep")
    period: Optional[str] = Field("14d", description="Timeframe: 7d, 14d, 1m, 3m, 6m, 1y")

class StoreScanResponse(BaseModel):
    store_name: str
    total_revenue: int
    total_profit: int
    avg_margin_percent: float
    
    monthly_chart: List[MonthlyData]
    seasonal_heatmap: List[SeasonalTrend]
    
    strong_cards: List[ProductAnalytics]
    weak_cards: List[ProductAnalytics]
    loss_making_cards: List[ProductAnalytics]
