import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from retailpool.routers.autoreply import _build_prompt, _generate_reply_ai

async def test_scenarios():
    scenarios = [
        {
            "desc": "1. Проблема с цветом самоката (Отзыв 1 звезда)",
            "question": "Ставлю 1 звезду! В карточке написано мультиколор, на фото желтый самокат, а пришел вообще зеленый! Я заказывала желтый ребенку!",
            "product_name": "Детский самокат трехколесный (мультиколор)",
            "customer_name": "Мадина",
            "settings": {"tone": "empathetic", "language": "ru", "store_description": "Магазин детских товаров."}
        },
        {
            "desc": "2. Не тот товар (Тасбих)",
            "question": "Таспих пришел не та которая была заказана вообще другой цвет и форма!",
            "product_name": "Электронный тасбих (счетчик)",
            "customer_name": "Айдос",
            "settings": {"tone": "professional", "language": "ru", "store_description": "Мусульманские товары."}
        },
        {
            "desc": "3. Поврежденный товар при доставке",
            "question": "Ужасно! Флакон открылся по дороге, весь шампунь вытек в пакет. Требую возврат денег!",
            "product_name": "Профессиональный шампунь для волос 1Л",
            "customer_name": "Елена",
            "settings": {"tone": "friendly", "language": "ru", "store_description": "Магазин косметики."}
        },
        {
            "desc": "4. Вопрос про Kaspi Red/Рассрочку",
            "question": "А можно этот телевизор через каспи ред взять на 3 месяца?",
            "product_name": "Телевизор LG 43 дюйма Smart TV",
            "customer_name": "Самат",
            "settings": {"tone": "professional", "language": "ru", "store_description": "Бытовая техника."}
        },
        {
            "desc": "5. Скрытый брак (проблема выявилась позже)",
            "question": "Купил регистратор неделю назад, а он теперь не включается и не заряжается. Куда нести по гарантии?",
            "product_name": "Видеорегистратор автомобильный 70mai",
            "customer_name": "Нурлан",
            "settings": {"tone": "professional", "language": "ru", "store_description": "Автотовары, гарантия на электронику 3 месяца."}
        }
    ]

    with open("results2.txt", "w", encoding="utf-8") as f:
        f.write("=== ТЕСТ: ЖЕСТКИЕ ПРЕТЕНЗИИ И ВОПРОСЫ ===\n")
        
        for idx, s in enumerate(scenarios):
            f.write(f"\n{s['desc']}\n")
            f.write(f"Покупатель ({s['customer_name']}): {s['question']}\n")
            
            prompt = _build_prompt(
                s["question"], 
                s["product_name"], 
                s["customer_name"], 
                s["settings"], 
                []
            )
            
            reply = await _generate_reply_ai(prompt)
            
            f.write(f"🤖 Ответ ИИ:\n{reply}\n")
            await asyncio.sleep(2)
            
if __name__ == "__main__":
    asyncio.run(test_scenarios())
