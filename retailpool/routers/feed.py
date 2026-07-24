"""
Kaspi XML Feed Generator for Preorders.
"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import xml.etree.ElementTree as ET
import datetime

from retailpool.database import get_db
from retailpool.models.ntin import UserSellerSettings
from retailpool.models.repricing import RepricingRule

router = APIRouter(prefix="/feed", tags=["XML Feed"])

@router.get("/{user_id}.xml")
async def generate_kaspi_feed(user_id: str, db: AsyncSession = Depends(get_db)):
    # 1. Validate user and get settings
    result = await db.execute(select(UserSellerSettings).where(UserSellerSettings.user_id == user_id))
    settings = result.scalar_one_or_none()
    
    company_name = settings.kaspi_shop_name if settings and settings.kaspi_shop_name else "Quareo Seller"
    merchant_id = settings.kaspi_merchant_id if settings and settings.kaspi_merchant_id else "123456"

    # 2. Get user's products
    result = await db.execute(select(RepricingRule).where(RepricingRule.user_id == user_id))
    products = result.scalars().all()

    # 3. Build XML
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    root = ET.Element("kaspi_catalog")
    root.set("date", now)
    root.set("xmlns", "kaspiShopping")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xsi:schemaLocation", "kaspiShopping http://kaspi.kz/kaspishopping.xsd")

    company = ET.SubElement(root, "company")
    company.text = str(company_name)
    
    merchant = ET.SubElement(root, "merchantid")
    merchant.text = str(merchant_id)

    offers = ET.SubElement(root, "offers")

    for p in products:
        offer = ET.SubElement(offers, "offer", sku=p.kaspi_sku)
        
        model = ET.SubElement(offer, "model")
        model.text = p.product_name
        
        price = ET.SubElement(offer, "price")
        price.text = str(int(p.my_current_price))

        availabilities = ET.SubElement(offer, "availabilities")
        
        # Ensure pre-order constraints (max 30)
        preorder = min(p.preorder_days, 30) if getattr(p, "preorder_days", None) else 0
        
        attrs = {
            "available": "yes",
            "store": "yes",
            "pickup": "yes",
            "delivery": "yes"
        }
        if preorder > 0:
            attrs["preorder"] = str(preorder)
            
        ET.SubElement(availabilities, "availability", **attrs)

    # 4. Return as application/xml
    xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return Response(content=xml_str, media_type="application/xml")
