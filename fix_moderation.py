import asyncio
import os
import re
import openpyxl
from dotenv import load_dotenv
from sqlalchemy import select
from retailpool.database import async_session_factory
from retailpool.models.ntin import NtinProduct, NtinStatus
import google.generativeai as genai

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# Use pro for better extraction
model = genai.GenerativeModel('gemini-2.5-pro')

def load_tnved():
    wb = openpyxl.load_workbook('product_request_template.xlsx', data_only=True)
    sheet = wb['ТНВЭД ЕАЭС']
    db = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row[0] and row[2]:
            db.append({"code": str(row[0]).strip(), "name": str(row[2])})
    return db

async def fix_revision_products():
    print("Loading TNVED db...")
    tnved_db = load_tnved()
    
    async with async_session_factory() as session:
        stmt = select(NtinProduct).where(NtinProduct.status == NtinStatus.REVISION)
        products = (await session.execute(stmt)).scalars().all()
        
        print(f"Found {len(products)} products in REVISION.")
        
        batch_size = 30
        for i in range(0, len(products), batch_size):
            batch = products[i:i+batch_size]
            prompt = (
                "Ты эксперт по классификации товаров (ТН ВЭД ЕАЭС). "
                "Для каждого товара в списке подбери наиболее точный 10-значный код ТН ВЭД. "
                "Также извлеки 'Бренд' из названия (если бренда нет, напиши 'Нет бренда'). "
                "Ответь СТРОГО в формате: ID|TNVED|БРЕНД (по одной строке на товар, без маркдауна и лишних слов).\n\n"
            )
            for p in batch:
                prompt += f"{p.id}|{p.title_ru}\n"
                
            try:
                resp = model.generate_content(prompt)
                lines = resp.text.strip().split('\n')
                
                for line in lines:
                    parts = line.split('|')
                    if len(parts) >= 3:
                        pid = parts[0].strip()
                        tnved = parts[1].strip().replace(" ", "").replace(".", "")
                        brand = parts[2].strip()
                        
                        # extract 10 digits
                        m = re.search(r'\d{10}', tnved)
                        if m:
                            tnved = m.group(0)
                        else:
                            tnved = "3926909709"
                            
                        # find in db
                        matched = None
                        for item in tnved_db:
                            if item['code'] == tnved:
                                matched = item['code']
                                break
                        if not matched:
                            for item in tnved_db:
                                if item['code'].startswith(tnved[:4]):
                                    matched = item['code']
                                    break
                        if not matched:
                            matched = "3926909709"
                            
                        # apply to product
                        for p in batch:
                            if str(p.id) == pid:
                                p.tn_ved_code = matched
                                p.brand = brand
                                p.status = NtinStatus.AI_FILLED
                                p.nkt_request_id = None
                                print(f"Fixed: {p.title_ru[:30]} -> {matched} | {brand}")
                                break
            except Exception as e:
                print(f"Batch error: {e}")
                
        await session.commit()
        print("Done!")

if __name__ == "__main__":
    asyncio.run(fix_revision_products())
