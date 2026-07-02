"""
Document handler — invoice generation and delivery via Telegram.
"""

from __future__ import annotations

import io
import logging

from telegram import Update
from telegram.ext import ContextTypes

from retailpool.bot.api_client import RetailPoolAPI
from retailpool.bot.keyboards import back_to_menu_keyboard
from retailpool.bot.pdf_generator import generate_invoice_pdf

logger = logging.getLogger(__name__)


async def document_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle document-related callbacks (doc:invoice:pool_id)."""
    query = update.callback_query
    await query.answer()

    data = query.data  # e.g. "doc:invoice:pool_id"
    parts = data.split(":")

    if len(parts) < 3:
        return

    action = parts[1]
    pool_id = parts[2]

    if action == "invoice":
        await _generate_and_send_invoice(query, pool_id)


async def _generate_and_send_invoice(query, pool_id: str) -> None:
    """Generate PDF invoice and send it as a document in chat."""
    await query.edit_message_text(
        "📄 Генерирую счёт...\n⏳ Подождите несколько секунд.",
    )

    try:
        # Get invoice data from backend
        invoice_data = await RetailPoolAPI.get_invoice(pool_id)

        # Generate PDF
        pdf_bytes = generate_invoice_pdf(invoice_data)

        # Send as document
        invoice_number = invoice_data.get("invoice_number", "invoice")
        filename = f"{invoice_number}.pdf"

        await query.message.reply_document(
            document=io.BytesIO(pdf_bytes),
            filename=filename,
            caption=(
                f"📄 <b>Счёт {invoice_number}</b>\n\n"
                f"Сумма: {_format_price(invoice_data.get('grand_total', 0))}\n"
                f"Вкл. комиссию: {_format_price(invoice_data.get('success_fee_amount', 0))}\n\n"
                "Перешлите этот документ бухгалтеру для оплаты."
            ),
            parse_mode="HTML",
        )

        await query.message.reply_text(
            "✅ Счёт успешно сгенерирован!",
            reply_markup=back_to_menu_keyboard(),
        )

    except Exception as exc:
        logger.error("Failed to generate invoice: %s", exc)
        await query.message.reply_text(
            f"❌ Ошибка при генерации счёта: <code>{exc}</code>",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )


def _format_price(price: float) -> str:
    return f"{int(price):,} ₸".replace(",", " ")
