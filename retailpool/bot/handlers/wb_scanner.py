"""
WB Scanner handler — analyze Wildberries niches from links or text queries.
"""

from __future__ import annotations

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from retailpool.scraper.wb_scraper import WBScraper
from retailpool.scraper.antifraud import StaticProxyProvider, SmartProxyProvider
from retailpool.bot.keyboards import back_to_menu_keyboard
from retailpool.config import settings

logger = logging.getLogger(__name__)

WAITING_FOR_WB_QUERY = 1

def _format_price(price: float) -> str:
    return f"{int(price):,} ₸".replace(",", " ")

async def wb_scanner_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user for a WB query."""
    text = (
        "🟣 *Сканер Wildberries (WB)*\n\n"
        "Отправьте мне поисковый запрос (например: `увлажнитель воздуха` или `iPhone 15`), "
        "и я найду самые популярные товары на WB, их цены и количество отзывов."
    )
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=back_to_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=back_to_menu_keyboard()
        )
        
    return WAITING_FOR_WB_QUERY

async def handle_wb_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the WB search query."""
    query = update.message.text.strip()
    
    msg = await update.message.reply_text("⏳ Ищу на Wildberries... Это займёт пару секунд.")
    
    try:
        # Choose proxy
        proxy_provider = None
        if settings.PROXY_URL:
            proxy_provider = StaticProxyProvider()
        elif settings.PROXY_PROVIDER_API_URL:
            proxy_provider = SmartProxyProvider()
            
        scraper = WBScraper(proxy_provider=proxy_provider)
        results = await scraper.search(query, max_items=10)
        
        if not results:
            await msg.edit_text(
                f"🤷‍♂️ Ничего не найдено по запросу: `{query}`.\nПопробуйте другой запрос.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Повторить", callback_data="menu:wb_scanner")]])
            )
            return ConversationHandler.END
            
        # Format results
        text = f"🟣 *Топ-товаров на WB по запросу «{query}»*\n\n"
        
        for i, p in enumerate(results, 1):
            price_rub_str = f"{int(p.price_rub):,} ₽".replace(",", " ")
            price_kzt_str = f"~ {int(p.price_kzt):,} ₸".replace(",", " ") if p.price_kzt else ""
            
            text += f"{i}. [{p.title}]({p.url})\n"
            text += f"   💰 *{price_rub_str}* ({price_kzt_str})\n"
            text += f"   💬 Отзывов: {p.review_count} ⭐ {p.rating or '-'}\n\n"
            
        text += "💡 Используйте эти данные, чтобы искать прибыльные связки между Kaspi и WB!"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Искать другой товар", callback_data="menu:wb_scanner")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="menu:main")]
        ])
        
        await msg.edit_text(text, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"WB Scraper bot error: {e}")
        await msg.edit_text(
            "❌ Произошла ошибка при сканировании WB. Попробуйте позже.",
            reply_markup=back_to_menu_keyboard()
        )
        
    return ConversationHandler.END

# ── Conversation Handler Export ──────────────────────────────────────────

wb_scanner_conv = ConversationHandler(
    entry_points=[
        CommandHandler("wb", wb_scanner_start),
        CallbackQueryHandler(wb_scanner_start, pattern=r"^menu:wb_scanner$")
    ],
    states={
        WAITING_FOR_WB_QUERY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wb_query),
        ]
    },
    fallbacks=[
        CallbackQueryHandler(lambda u, c: ConversationHandler.END, pattern=r"^menu:main$")
    ],
    name="wb_scanner_conv",
    persistent=False,
)
