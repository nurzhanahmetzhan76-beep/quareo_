import asyncio
import uuid
from sqlalchemy import select
from retailpool.database import async_session_factory
from retailpool.models.ntin import NtinProduct, NtinStatus
from retailpool.services.ntin_service import NtinService

async def fix_rejected_products():
    """Find products with bad OKTRU codes and re-process them."""
    bad_codes = ["1106-0001-0001-100011943", "3203-0001-0001-100017260"]
    
    async with async_session_factory() as session:
        # Find all products with bad OKTRU
        stmt = select(NtinProduct).where(NtinProduct.oktru_code.in_(bad_codes))
        result = await session.execute(stmt)
        products = result.scalars().all()
        
        print(f"Найдено {len(products)} товаров с неверным ОКТРУ ('буровые станки').")
        
        if not products:
            print("Нечего исправлять.")
            return

        # 1. Reset them to DRAFT and clear oktru
        for p in products:
            p.oktru_code = None
            p.status = NtinStatus.DRAFT
            p.nkt_request_id = None
            p.ntin_code = None
            p.revision_comment = "Сброшено для исправления категории ОКТРУ"
            
        await session.commit()
        print(f"✅ Успешно сброшен статус и очищен ОКТРУ для {len(products)} товаров.")
        print("Теперь вы можете зайти в панель NTIN и нажать 'Запустить AI-заполнение', чтобы Groq подобрал правильные категории.")

if __name__ == "__main__":
    asyncio.run(fix_rejected_products())
