"""
Auth handler — Telegram bot login and plan verification.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop
import httpx

from retailpool.bot.config import bot_settings

logger = logging.getLogger(__name__)


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /login <email> <password> command."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "🔑 <b>Авторизация</b>\n\n"
            "Использование: <code>/login ваш_email пароль</code>\n\n"
            "Пример:\n<code>/login ivan@mail.ru 12345678</code>",
            parse_mode="HTML"
        )
        return

    email = context.args[0]
    password = context.args[1]

    await update.message.reply_text("⏳ Проверка данных...")

    try:
        async with httpx.AsyncClient(base_url=bot_settings.API_BASE_URL) as client:
            resp = await client.post("/auth/login", json={"email": email, "password": password})
            
            if resp.status_code == 200:
                data = resp.json()
                user = data.get("user", {})
                plan = user.get("plan", "free")
                
                context.user_data["email"] = email
                context.user_data["plan"] = plan
                context.user_data["token"] = data.get("access_token")
                
                if plan.lower() == "unlimited" or email == "karimbai.ali10@mail.ru":
                    chat_id = update.effective_chat.id
                    headers = {"Authorization": f"Bearer {data.get('access_token')}"}
                    try:
                        link_resp = await client.post("/auth/telegram-link", json={"telegram_id": chat_id}, headers=headers)
                        if link_resp.status_code != 200:
                            logger.error("Failed to link telegram: %s", link_resp.text)
                    except Exception as e:
                        logger.error("Error linking telegram: %s", e)

                    await update.message.reply_text(
                        "✅ <b>Успешная авторизация!</b>\n\n"
                        "Ваш тариф: <b>Безлимит</b>.\n"
                        "Теперь вам доступны все функции бота, а также вы будете автоматически получать сливы горячих ниш с сайта!",
                        parse_mode="HTML"
                    )
                else:
                    await update.message.reply_text(
                        f"⚠️ Вы вошли как {email}, но ваш тариф: <b>{plan}</b>.\n\n"
                        "Бот доступен только для тарифа <b>Безлимит</b>. Пожалуйста, обновите тариф на платформе.",
                        parse_mode="HTML"
                    )
            else:
                await update.message.reply_text(
                    "❌ Неверный email или пароль. Проверьте данные и попробуйте снова."
                )
    except Exception as e:
        logger.error("Login error: %s", e)
        await update.message.reply_text("❌ Произошла ошибка при подключении к серверу.")


async def auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Middleware to block users without the Unlimited plan."""
    # Allow safe commands to pass
    if update.message and update.message.text:
        text = update.message.text
        if text.startswith("/start") or text.startswith("/help") or text.startswith("/login"):
            return

    # Check authorization and plan
    plan = context.user_data.get("plan", "free")
    email = context.user_data.get("email", "")

    if plan.lower() == "unlimited" or email == "karimbai.ali10@mail.ru":
        return  # Pass through to the next handlers

    # Block access
    msg = (
        "❌ <b>Доступ запрещен</b>\n\n"
        "Этот бот — эксклюзивный инструмент для пользователей тарифа <b>Безлимит</b>.\n\n"
        "Пожалуйста, авторизуйтесь с помощью команды:\n"
        "<code>/login ваш_email пароль</code>"
    )

    if update.callback_query:
        await update.callback_query.answer("Доступ запрещен (нужен тариф Безлимит)", show_alert=True)
    elif update.message:
        await update.message.reply_text(msg, parse_mode="HTML")

    raise ApplicationHandlerStop()
