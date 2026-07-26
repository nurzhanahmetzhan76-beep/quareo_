import asyncio
import uuid
from sqlalchemy import select
from retailpool.database import SessionLocal
from retailpool.models.user import User
from retailpool.models.ntin import UserSellerSettings
from retailpool.models.repricing import RepricingRule, RepricingLog
import xml.etree.ElementTree as ET
import pytest
from httpx import AsyncClient
from retailpool.main import app
import os

async def run_test():
    async with SessionLocal() as db:
        # Create a mock user
        test_user_id = uuid.uuid4()
        user = User(id=test_user_id, email=f"test_{test_user_id}@mail.ru", hashed_password="pw", is_active=True)
        db.add(user)
        await db.commit()

        # Create settings pointing to a local file
        settings = UserSellerSettings(
            user_id=test_user_id,
            kaspi_xml_url=f"https://quareo.pro/assets/feeds/{test_user_id}.xml"
        )
        db.add(settings)

        # Create a RepricingRule for SKU "12345"
        rule = RepricingRule(
            user_id=test_user_id,
            product_name="Test Product",
            kaspi_sku="12345",
            my_current_price=1500,
            min_price=1000,
            is_active=True,
            last_competitor_price=1400
        )
        db.add(rule)
        
        # Create a RepricingRule for SKU "99999" (floor hit)
        rule2 = RepricingRule(
            user_id=test_user_id,
            product_name="Test Product 2",
            kaspi_sku="99999",
            my_current_price=800, # Will hit floor of 1000
            min_price=1000,
            is_active=True,
            last_competitor_price=800
        )
        db.add(rule2)
        await db.commit()

        # Create a mock ACTIVE (3).xml feed
        xml_content = """<?xml version="1.0" encoding="utf-8"?>
<kaspi_catalog date="2026-07-26 12:00" xmlns="kaspiShopping" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="kaspiShopping http://kaspi.kz/kaspishopping.xsd">
    <company>Test Seller</company>
    <merchantid>TestMerchant</merchantid>
    <offers>
        <offer sku="12345">
            <model>Product 1</model>
            <brand>Brand 1</brand>
            <price>2000</price>
            <availabilities>
                <availability available="yes" storeId="PP1" stockCount="50.0" preOrder="0"/>
            </availabilities>
        </offer>
        <offer sku="99999">
            <model>Product 2</model>
            <brand>Brand 2</brand>
            <price>2000</price>
            <availabilities>
                <availability available="yes" storeId="PP1" stockCount="10.0" preOrder="0"/>
            </availabilities>
        </offer>
    </offers>
</kaspi_catalog>"""
        
        # Save it to the expected path
        feeds_dir = os.path.join("frontend", "assets", "feeds")
        os.makedirs(feeds_dir, exist_ok=True)
        file_path = os.path.join(feeds_dir, f"{test_user_id}.xml")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        print(f"Created mock feed at {file_path}")

        # Execute endpoint
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get(f"/api/feed/{test_user_id}.xml")
            print("Response Status:", response.status_code)
            xml_resp = response.text
            print("Response XML Output:\n", xml_resp)
            
            # Check if prices updated correctly
            assert "<price>1500</price>" in xml_resp
            assert "<price>1000</price>" in xml_resp # floor price
            assert "stockCount=\"50.0\"" in xml_resp # preserved stock
            assert "kaspiShopping" in xml_resp # namespaces intact
            
            # Check Audit Logs
            logs = await db.execute(select(RepricingLog).where(RepricingLog.rule_id.in_([rule.id, rule2.id])))
            all_logs = logs.scalars().all()
            print(f"Found {len(all_logs)} Audit Logs")
            for log in all_logs:
                print(f"Log: Rule {log.rule_id}, Old {log.old_price}, New {log.new_price}, Action {log.action}")

if __name__ == "__main__":
    asyncio.run(run_test())
