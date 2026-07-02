"""
Alert handler — push notification subscriptions for dumping & stock-out tracking.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes

from retailpool.bot.keyboards import (
    alert_list_keyboard,
    alert_type_keyboard,
    back_to_menu_keyboard,
)

logger = logging.getLogger(__name__)

# In-memory alert storage (will be moved to DB via models.py + Alembic)
# Structure: {user_id: [{"id": str, "query": str, "type": str, "active": bool, ...}]}
_alert_store: dict[int, list[dict]] = {}


def _get_user_alerts(user_id: int) -> list[dict]:
    """Get active alerts for a user."""
    return [a for a in _alert_store.get(user_id, []) if a.get("active", True)]


def _add_alert(user_id: int, query: str, alert_type: str) -> dict:
    """Add a new alert subscription."""
    alert = {
        "id": uuid.uuid4().hex[:8],
        "query": query,
        "type": alert_type,
        "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_snapshot": None,
        "last_checked_at": None,
    }
    if user_id not in _alert_store:
        _alert_store[user_id] = []
    _alert_store[user_id].append(alert)
    logger.info("Alert created for user %d: %s (%s)", user_id, query, alert_type)
    return alert


def _remove_alert(user_id: int, alert_id: str) -> bool:
    """Deactivate an alert."""
    for alert in _alert_store.get(user_id, []):
        if alert["id"] == alert_id:
            alert["active"] = False
            return True
    return False


# ── Command: /alerts ─────────────────────────────────────────────────────

async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /alerts command — show active subscriptions."""
    user_id = update.effective_user.id
    alerts = _get_user_alerts(user_id)

    if not alerts:
        await update.message.reply_text(
            "🔔 <b>Мои алерты</b>\n\n"
            "У вас пока нет активных подписок.\n\n"
            "Используйте <code>/track запрос</code> чтобы\n"
            "отслеживать демпинг и стоки конкурентов.\n\n"
            "Пример: <code>/track наушники TWS</code>",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    text = _format_alerts_list(alerts)
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=alert_list_keyboard(alerts),
    )


async def show_alerts_list(
    query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show alerts from menu callback."""
    user_id = query.from_user.id
    alerts = _get_user_alerts(user_id)

    if not alerts:
        await query.edit_message_text(
            "🔔 <b>Мои алерты</b>\n\n"
            "У вас пока нет активных подписок.\n\n"
            "Используйте <code>/track запрос</code> чтобы\n"
            "отслеживать демпинг и стоки конкурентов.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    text = _format_alerts_list(alerts)
    await query.edit_message_text(
        text,
        parse_mode="HTML",
        reply_markup=alert_list_keyboard(alerts),
    )


def _format_alerts_list(alerts: list[dict]) -> str:
    """Format alerts into a text list."""
    lines = ["🔔 <b>Мои алерты</b>\n"]
    type_labels = {
        "dumping": "📉 Демпинг",
        "stock_out": "📦 Stock-out",
        "both": "📉+📦 Оба",
    }
    for i, a in enumerate(alerts, 1):
        type_label = type_labels.get(a["type"], a["type"])
        lines.append(
            f"{i}. <b>{a['query']}</b>\n"
            f"   Тип: {type_label} | ID: <code>{a['id']}</code>"
        )
    lines.append("\nНажмите 🔕 чтобы отписаться.")
    return "\n".join(lines)


# ── Command: /track ──────────────────────────────────────────────────────

async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /track <query> — subscribe to alerts for a niche."""
    if not context.args:
        await update.message.reply_text(
            "🔔 Использование: <code>/track запрос</code>\n\n"
            "Пример: <code>/track наушники TWS</code>\n\n"
            "Я буду отслеживать демпинг и стоки\n"
            "конкурентов в этой нише.",
            parse_mode="HTML",
        )
        return

    query_text = " ".join(context.args)
    await update.message.reply_text(
        f"🔔 <b>Новый алерт: «{query_text}»</b>\n\n"
        "Выберите тип отслеживания:",
        parse_mode="HTML",
        reply_markup=alert_type_keyboard(query_text),
    )


# ── Command: /untrack ────────────────────────────────────────────────────

async def untrack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /untrack <id> — unsubscribe from an alert."""
    if not context.args:
        await update.message.reply_text(
            "Использование: <code>/untrack ID</code>\n\n"
            "Посмотрите ID в /alerts",
            parse_mode="HTML",
        )
        return

    alert_id = context.args[0]
    user_id = update.effective_user.id

    if _remove_alert(user_id, alert_id):
        await update.message.reply_text(
            f"✅ Алерт <code>{alert_id}</code> отключён.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            f"❌ Алерт <code>{alert_id}</code> не найден.",
            parse_mode="HTML",
        )


# ── Callbacks ────────────────────────────────────────────────────────────

async def alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle alert-related callback queries."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split(":")

    if len(parts) < 3:
        return

    action = parts[1]

    if action == "unsub":
        alert_id = parts[2]
        user_id = query.from_user.id
        if _remove_alert(user_id, alert_id):
            await query.edit_message_text(
                f"✅ Алерт <code>{alert_id}</code> отключён.",
                parse_mode="HTML",
                reply_markup=back_to_menu_keyboard(),
            )
        else:
            await query.edit_message_text(
                f"❌ Алерт не найден.",
                reply_markup=back_to_menu_keyboard(),
            )

    elif action == "type":
        # alert:type:dumping:query
        if len(parts) >= 4:
            alert_type = parts[2]
            alert_query = ":".join(parts[3:])  # Rejoin in case query had colons
            user_id = query.from_user.id

            alert = _add_alert(user_id, alert_query, alert_type)

            type_labels = {
                "dumping": "📉 Демпинг",
                "stock_out": "📦 Stock-out",
                "both": "📉+📦 Оба",
            }

            await query.edit_message_text(
                f"✅ <b>Алерт создан!</b>\n\n"
                f"Запрос: <b>{alert_query}</b>\n"
                f"Тип: {type_labels.get(alert_type, alert_type)}\n"
                f"ID: <code>{alert['id']}</code>\n\n"
                f"Я буду проверять нишу каждые 30 мин и пришлю\n"
                f"уведомление при обнаружении изменений.",
                parse_mode="HTML",
                reply_markup=back_to_menu_keyboard(),
            )

    elif action == "new":
        context.user_data["creating_alert"] = True
        await query.edit_message_text(
            "🔔 <b>Новый алерт</b>\n\n"
            "Отправьте запрос для отслеживания:\n"
            "Например: <code>наушники TWS</code>",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )


async def alert_text_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle text input when creating a new alert."""
    if not context.user_data.get("creating_alert"):
        return

    context.user_data.pop("creating_alert", None)
    query_text = update.message.text.strip()

    await update.message.reply_text(
        f"🔔 <b>Новый алерт: «{query_text}»</b>\n\n"
        "Выберите тип отслеживания:",
        parse_mode="HTML",
        reply_markup=alert_type_keyboard(query_text),
    )


# ── Public API for alert_worker ──────────────────────────────────────────

def get_all_active_alerts() -> dict[int, list[dict]]:
    """Get all active alerts across all users (for the worker)."""
    result = {}
    for user_id, alerts in _alert_store.items():
        active = [a for a in alerts if a.get("active", True)]
        if active:
            result[user_id] = active
    return result


def update_alert_snapshot(user_id: int, alert_id: str, snapshot: dict) -> None:
    """Update last_snapshot for an alert after checking."""
    for alert in _alert_store.get(user_id, []):
        if alert["id"] == alert_id:
            alert["last_snapshot"] = snapshot
            alert["last_checked_at"] = datetime.now(timezone.utc).isoformat()
            break
