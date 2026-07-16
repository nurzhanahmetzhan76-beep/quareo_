import asyncio
import re
import openpyxl
from sqlalchemy import select
from retailpool.database import async_session_factory
from retailpool.models.ntin import NtinProduct, NtinStatus

def load_tnved():
    wb = openpyxl.load_workbook('product_request_template.xlsx', data_only=True)
    sheet = wb['ТНВЭД ЕАЭС']
    db = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row[0] and row[2]:
            db.append({"code": str(row[0]).strip(), "name": str(row[2]).lower()})
    return db

def clean_title(title: str) -> str:
    # Remove trailing SKUs (numbers, underscores, dashes at the end)
    cleaned = re.sub(r'\s+[\d\_\-]+$', '', title.strip())
    cleaned = re.sub(r'\s+[A-Za-z0-9\-\_]{5,}$', '', cleaned)
    return cleaned.strip()

def get_best_tnved(title: str, tnved_db: list) -> str:
    tl = title.lower()
    
    overrides = {
        "машинка": "9503007000",
        "игрушк": "9503007000",
        "чехол": "4202990000",
        "массажер": "9019109001",
        "подушк": "9404909000",
        "пакет": "3923210000",
        "пленк": "3920999000",
        "наушник": "8518300000",
        "кабель": "8544429009",
        "зарядн": "8504409000",
        "стекло": "7007290000",
        "ремень": "4203300000",
        "часы": "9102120000",
        "копилк": "3926400000",
        "пенал": "4202321000",
        "шторк": "6303929000",
    }
    
    for k, v in overrides.items():
        if k in tl:
            return v
            
    # Fuzzy match using whole words
    words = [w for w in re.findall(r'[а-яА-Я]{4,}', tl)]
    if words:
        for w in words:
            # try to find the word in the db
            for item in tnved_db:
                if re.search(r'\b' + re.escape(w[:-1]) + r'[а-я]*\b', item['name']):
                    return item['code']
                    
    return "3926909709"

async def fix_revision_products():
    print("Loading TNVED db...")
    tnved_db = load_tnved()
    
    async with async_session_factory() as session:
        stmt = select(NtinProduct).where(NtinProduct.status == NtinStatus.REVISION)
        products = (await session.execute(stmt)).scalars().all()
        
        print(f"Found {len(products)} products in REVISION.")
        
        updated = 0
        for p in products:
            new_title = clean_title(p.title_ru)
            if new_title != p.title_ru:
                p.title_ru = new_title
                
            if not p.brand or p.brand.lower() in ["none", "отсутствует", "не указано"]:
                p.brand = "Нет бренда"
                
            best_code = get_best_tnved(new_title, tnved_db)
            p.tn_ved_code = best_code
            
            p.status = NtinStatus.AI_FILLED
            p.nkt_request_id = None
            updated += 1
            
        await session.commit()
        print(f"Fixed {updated} products!")

asyncio.run(fix_revision_products())
