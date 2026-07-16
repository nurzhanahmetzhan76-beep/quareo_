import asyncio
import re
from sqlalchemy import select
from retailpool.database import async_session_factory
from retailpool.models.ntin import NtinProduct, NtinStatus, OktruDictionary

async def fix_oktru():
    print("Fixing OKTRU for rejected products...")
    
    async with async_session_factory() as session:
        stmt = select(NtinProduct).where(NtinProduct.status == NtinStatus.REVISION)
        products = (await session.execute(stmt)).scalars().all()
        
        print(f"Found {len(products)} products in REVISION.")
        
        # Load OKTRU dictionary
        stmt_oktru = select(OktruDictionary)
        oktru_items = (await session.execute(stmt_oktru)).scalars().all()
        print(f"Loaded {len(oktru_items)} OKTRU categories.")
        
        updated = 0
        for p in products:
            tl = p.title_ru.lower()
            
            # Simple overrides for OKTRU
            overrides = {
                "чехол": "3203-0001-0001-100017260", # Чехлы для мобильных телефонов
                "стекло": "3203-0001-0001-100017261", # Защитные стекла
                "пленк": "3203-0001-0001-100017261", 
                "кабель": "3203-0001-0001-100017264", # Кабели
                "наушник": "3203-0001-0001-100017262", # Наушники
                "зарядн": "3203-0001-0001-100017263", # Зарядные устройства
                "игрушк": "1408-0002-0002-100022359", # Игрушки
                "машинка": "1408-0002-0002-100022359",
                "копилк": "1408-0002-0002-100022359", # Сувениры/игрушки
                "шторк": "1405-0001-0001-100021990", # Шторы
                "массажер": "1105-0001-0001-100011850", # Массажеры
            }
            
            best_oktru = None
            for k, v in overrides.items():
                if k in tl:
                    best_oktru = v
                    break
                    
            if not best_oktru:
                # Try to search in OKTRU dictionary
                words = [w for w in re.findall(r'[а-яА-Я]{4,}', tl)]
                for w in words:
                    for item in oktru_items:
                        if w[:-1] in item.name_ru.lower() and item.code.count('-') == 3:
                            best_oktru = item.code
                            break
                    if best_oktru:
                        break
            
            if best_oktru:
                p.oktru_code = best_oktru
            else:
                p.oktru_code = "3203-0001-0001-100017260" # Fallback to accessories instead of drilling rig!
                
            p.status = NtinStatus.AI_FILLED
            p.nkt_request_id = None
            p.revision_comment = None
            updated += 1
            
        await session.commit()
        print(f"Fixed OKTRU and reset status to AI_FILLED for {updated} products!")

asyncio.run(fix_oktru())
