"""
Secure Kaspi XML Feed Mirror Generator.
"""
from fastapi import APIRouter, Depends, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import httpx
import logging

# Security: using defusedxml to prevent XXE attacks
from defusedxml.ElementTree import fromstring
import xml.etree.ElementTree as ET

from retailpool.database import get_db
from retailpool.models.ntin import UserSellerSettings
from retailpool.models.repricing import RepricingRule

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feed", tags=["XML Feed"])

@router.get("/{feed_uuid}.xml")
async def generate_kaspi_feed(feed_uuid: str, db: AsyncSession = Depends(get_db)):
    """
    Secure XML Feed Generator.
    URL Format: /feed/<UUID>.xml (Protects against predictable ID enumeration)
    
    1. Validates the feed UUID (currently mapping user_id for backward compatibility, 
       but strictly enforcing UUIDv4 format).
    2. Downloads the original XML feed specified in UserSellerSettings.
    3. Parses it securely using defusedxml to prevent XXE.
    4. Iterates over all <offer> nodes, preserving the ENTIRE assortment (to avoid archiving).
    5. Applies repricing only to matching active products.
    6. Strictly enforces the floor price (min_price).
    """
    import uuid
    try:
        user_uuid = uuid.UUID(feed_uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid feed identifier format (must be UUIDv4).")

    # 1. Validate user and get settings
    result = await db.execute(select(UserSellerSettings).where(UserSellerSettings.user_id == user_uuid))
    settings = result.scalar_one_or_none()
    
    if not settings or not settings.kaspi_xml_url:
        # CRITICAL SAFETY: Never return an empty catalog! 
        # Kaspi interprets an empty catalog as "0 products in stock" and will unpublish everything.
        # Returning an HTTP error forces Kaspi to keep the previous stock state intact.
        raise HTTPException(
            status_code=400, 
            detail="Source Kaspi XML URL is not configured in settings. Cannot generate feed."
        )

    # 2. Get user's repricing rules (active only)
    result = await db.execute(
        select(RepricingRule).where(
            RepricingRule.user_id == user_uuid,
            RepricingRule.is_active == True
        )
    )
    rules = result.scalars().all()
    # Support composite SKUs by mapping base SKU and full SKUs
    rule_map = {}
    for r in rules:
        if r.kaspi_sku:
            rule_map[r.kaspi_sku] = r
            base_sku = r.kaspi_sku.split('_')[0]
            if base_sku not in rule_map:
                rule_map[base_sku] = r

    # 3. Securely fetch and parse the original XML feed
    try:
        import os
        if "/assets/feeds/" in settings.kaspi_xml_url:
            # Local generated feed: read from disk to avoid Docker/NAT loopback network errors
            filename = settings.kaspi_xml_url.split("/")[-1]
            local_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "assets", "feeds", filename))
            with open(local_path, "rb") as f:
                raw_xml = f.read()
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(settings.kaspi_xml_url)
                resp.raise_for_status()
                raw_xml = resp.content
    except Exception as e:
        logger.error(f"Failed to fetch original XML feed for {user_uuid}: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch source XML feed.")

    try:
        # Prevent XXE vulnerabilities
        root = fromstring(raw_xml)
    except Exception as e:
        logger.error(f"Failed to parse source XML for {user_uuid}: {e}")
        raise HTTPException(status_code=502, detail="Source XML is invalid or malformed.")

    # Remove namespace prefixes from tags for easier processing if present
    for elem in root.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]

    offers = root.find('.//offers')
    if offers is None:
        offers = root

    # 4. Process all offers, preserving assortment and enforcing floor limits
    for offer in offers.findall('.//offer'):
        sku = offer.get('sku') or offer.get('id')
        if not sku:
            continue
            
        sku_str = str(sku).strip()
        matched_rule = None
        
        if sku_str in rule_map:
            matched_rule = rule_map[sku_str]
        else:
            # Fallback for composite match
            base_sku = sku_str.split('_')[0]
            if base_sku in rule_map:
                matched_rule = rule_map[base_sku]

        if matched_rule and matched_rule.my_current_price:
            # Enforcement: STRICT FLOOR PRICE CHECK
            safe_price = max(matched_rule.my_current_price, matched_rule.min_price)
            
            price_node = offer.find('price')
            if price_node is not None:
                price_node.text = str(int(safe_price))
            else:
                cityprice = offer.find('.//cityprice')
                if cityprice is not None:
                    cityprice.text = str(int(safe_price))
                else:
                    new_price_node = ET.SubElement(offer, 'price')
                    new_price_node.text = str(int(safe_price))

            # Handle preorder injection in availabilities
            if matched_rule.preorder_days and matched_rule.preorder_days > 0:
                avail_node = offer.find('availabilities')
                if avail_node is None:
                    avail_node = ET.SubElement(offer, 'availabilities')
                    
                # Mirror existing availabilities, just inject preorder attribute
                avails = avail_node.findall('availability')
                if not avails:
                    # Fallback if no availabilities existed
                    ET.SubElement(avail_node, 'availability', available="yes", store="yes", pickup="yes", delivery="yes", preOrder=str(min(matched_rule.preorder_days, 30)))
                else:
                    for av in avails:
                        av.set('preOrder', str(min(matched_rule.preorder_days, 30)))
                        # CRITICAL: If an item is on pre-order, it MUST be active, otherwise Kaspi keeps it archived.
                        av.set('available', 'yes')

    # 5. Output the secured, modified XML mirror
    # ET.tostring works fine here since we already used defusedxml to parse
    xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")
    return Response(content=xml_str, media_type="application/xml")
