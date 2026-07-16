import asyncio
import openpyxl
from retailpool.database import async_session_factory
from retailpool.models.ntin import NtinProduct, NtinStatus
from sqlalchemy import select

def load_tnved():
    wb = openpyxl.load_workbook('product_request_template.xlsx', data_only=True)
    sheet = wb['ТНВЭД ЕАЭС']
    db = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row[0] and row[2]:
            db.append({"code": str(row[0]), "name": str(row[2]).lower()})
    return db

async def fix_products():
    print("Loading TNVED db from Excel...")
    tnved_db = load_tnved()
    print(f"Loaded {len(tnved_db)} TNVED codes.")
    
    async with async_session_factory() as session:
        stmt = select(NtinProduct).where(
            NtinProduct.status == NtinStatus.SUBMITTED,
            NtinProduct.tn_ved_code.is_(None)
        )
        result = await session.execute(stmt)
        products = result.scalars().all()
        
        updated = 0
        for p in products:
            keywords = p.title_ru.lower().replace(",", "").replace("-", " ").split()
            best_code = None
            
            if keywords:
                root = keywords[0][:5]
                # find first match
                for item in tnved_db:
                    if root in item["name"]:
                        best_code = item["code"]
                        break
            
            if not best_code:
                # 3926909709 - Прочие изделия из пластмасс
                best_code = "3926909709"
                
            p.tn_ved_code = best_code
            if not p.unit_of_measure:
                p.unit_of_measure = "шт"
                
            # Reset status so they can be submitted again
            p.status = NtinStatus.AI_FILLED
            p.nkt_request_id = None
            updated += 1
            
        await session.commit()
        print(f"Fixed {updated} products!")

asyncio.run(fix_products())
