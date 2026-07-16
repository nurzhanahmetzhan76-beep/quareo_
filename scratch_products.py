import asyncio
from collections import Counter
from retailpool.database import async_session_factory
from retailpool.models.ntin import NtinProduct
from sqlalchemy import select

async def get_products():
    async with async_session_factory() as session:
        stmt = select(NtinProduct.title_ru)
        titles = (await session.execute(stmt)).scalars().all()
        
        with open('products_sample.txt', 'w', encoding='utf-8') as f:
            f.write(f'Total products: {len(titles)}\n')
            
            words = []
            for t in titles:
                if t:
                    for w in t.lower().split():
                        if len(w) > 3:
                            words.append(w)
                        
            counter = Counter(words)
            f.write('Most common words:\n')
            for w, c in counter.most_common(50):
                f.write(f'{w}: {c}\n')
            
            f.write('\nSample products:\n')
            import random
            for t in random.sample(titles, min(30, len(titles))):
                f.write(f'- {t}\n')

asyncio.run(get_products())
