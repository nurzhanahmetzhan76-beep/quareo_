"""
Products handler — manage user products and pre-order settings.
"""

from __future__ import annotations

import logging
import httpx

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from retailpool.bot.config import bot_settings
from retailpool.bot.keyboards import back_to_menu_keyboard

logger = logging.getLogger(__name__)

async def products_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the list of products for the user to manage."""
    token = context.user_data.get("token")
    if not token:
        await _auth_required(update)
        return

    # Fetch rules
    try:
        async with httpx.AsyncClient(base_url=bot_settings.API_BASE_URL) as client:
            resp = await client.get("/api/repricing/rules", headers={"Authorization": f"Bearer {token}"})
            if resp.status_code != 200:
                await _error_msg(update, "Не удалось загрузить список товаров.")
                return
            rules = resp.json()
    except Exception as e:
        logger.error("Failed to fetch products: %s", e)
        await _error_msg(update, "Ошибка сети при загрузке товаров.")
        return

    if not rules:
        text = (
            "📦 <b>Мои товары</b>\n\n"
            "У вас пока нет добавленных товаров в репрайсинге.\n"
            "Добавьте их через веб-панель Quareo."
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())
        else:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())
        return

    text = "📦 <b>Управление предзаказом</b>\n\nВыберите товар из списка ниже:"
    
    # We will just list the first 20 products for simplicity in the bot
    keyboard = []
    for r in rules[:20]:
        title = r.get("product_name", "Товар")[:30]
        preorder = r.get("preorder_days", 0)
        status = f"(Предзаказ: {preorder} дн.)" if preorder > 0 else ""
        btn_text = f"{title} {status}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"prod:preorder:{r['id']}")])
    
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="menu:main")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)


async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle product-related callbacks (e.g. prod:preorder:uuid)."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split(":")
    if len(parts) < 3:
        return

    action = parts[1]
    rule_id = parts[2]

    if action == "preorder":
        context.user_data["waiting_for_preorder"] = rule_id
        text = (
            "⏳ <b>Настройка предзаказа</b>\n\n"
            "За сколько дней товар доедет до клиента?\n"
            "Введите число от 1 до 30 (или 0 для отключения предзаказа):"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="menu:products")]
        ])
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def handle_preorder_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text input for preorder days."""
    rule_id = context.user_data.get("waiting_for_preorder")
    if not rule_id:
        return

    text = update.message.text.strip()
    try:
        days = int(text)
        if days < 0 or days > 30:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите корректное число от 0 до 30.")
        return

    token = context.user_data.get("token")
    if not token:
        await _auth_required(update)
        return

    # Clear state
    context.user_data.pop("waiting_for_preorder", None)

    # Patch the rule via API
    try:
        async with httpx.AsyncClient(base_url=bot_settings.API_BASE_URL) as client:
            resp = await client.patch(
                f"/api/repricing/rules/{rule_id}",
                json={"preorder_days": days},
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code != 200:
                await update.message.reply_text("❌ Ошибка при сохранении настроек.")
                return
    except Exception as e:
        logger.error("Failed to update preorder: %s", e)
        await update.message.reply_text("❌ Ошибка сети при сохранении.")
        return

    success_msg = f"✅ <b>Предзаказ успешно установлен на {days} дней.</b>"
    if days == 0:
        success_msg = "✅ <b>Предзаказ отключен. Товар переведен в режим обычной продажи.</b>"
        
    warning_msg = (
        "\n\n⚠️ <b>Внимание!</b> Пока товар на предзаказе, не меняйте его цену вручную "
        "в приложении Kaspi Pay, иначе предзаказ слетит. Меняйте цену только через Quareo."
    )
    
    await update.message.reply_text(
        success_msg + warning_msg,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К списку товаров", callback_data="menu:products")]])
    )


async def _auth_required(update: Update):
    text = "Для этого действия необходима авторизация. Используйте команду /login"
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    elif update.message:
        await update.message.reply_text(text)

async def _error_msg(update: Update, text: str):
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=back_to_menu_keyboard())
    elif update.message:
        await update.message.reply_text(text, reply_markup=back_to_menu_keyboard())
