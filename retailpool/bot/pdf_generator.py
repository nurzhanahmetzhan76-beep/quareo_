"""
PDF Invoice Generator using ReportLab.

Generates professional-looking PDF invoices for co-buying pool payments.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

logger = logging.getLogger(__name__)


def _format_price(price: float) -> str:
    """Format price in tenge."""
    return f"{int(price):,} ₸".replace(",", " ")


def generate_invoice_pdf(invoice_data: dict) -> bytes:
    """
    Generate a PDF invoice from invoice payload data.

    Args:
        invoice_data: JSON payload from /documents/invoice endpoint

    Returns:
        PDF file as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#1a1a2e"),
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    subtitle_style = ParagraphStyle(
        "InvoiceSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#666666"),
        alignment=TA_CENTER,
        spaceAfter=20,
    )

    info_style = ParagraphStyle(
        "InfoStyle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#333333"),
        spaceAfter=4,
    )

    total_style = ParagraphStyle(
        "TotalStyle",
        parent=styles["Normal"],
        fontSize=12,
        textColor=colors.HexColor("#1a1a2e"),
        alignment=TA_RIGHT,
        fontName="Helvetica-Bold",
    )

    # Build document elements
    elements = []

    # ── Header ───────────────────────────────────────────────────────────
    elements.append(Paragraph("RetailPool AI", title_style))
    elements.append(
        Paragraph("Платформа совместных закупок | Kaspi.kz", subtitle_style)
    )
    elements.append(Spacer(1, 10))

    # ── Invoice info ─────────────────────────────────────────────────────
    inv_number = invoice_data.get("invoice_number", "—")
    generated_at = invoice_data.get("generated_at", "")
    pool_id = str(invoice_data.get("pool_id", "—"))

    if isinstance(generated_at, str) and generated_at:
        try:
            dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            date_str = dt.strftime("%d.%m.%Y %H:%M")
        except Exception:
            date_str = generated_at
    else:
        date_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    info_data = [
        ["Счёт №:", inv_number],
        ["Дата:", date_str],
        ["Пул ID:", pool_id[:16] + "..."],
    ]

    info_table = Table(info_data, colWidths=[100, 350])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#333333")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))

    # ── Line items table ─────────────────────────────────────────────────
    elements.append(Paragraph(
        "<b>Позиции</b>",
        ParagraphStyle("SectionHeader", parent=styles["Normal"], fontSize=12,
                       textColor=colors.HexColor("#1a1a2e"), spaceAfter=8),
    ))

    items = invoice_data.get("items", [])
    table_data = [["№", "Товар", "Кол-во", "Цена/шт", "Сумма"]]

    for i, item in enumerate(items, 1):
        table_data.append([
            str(i),
            item.get("product_name", "—")[:40],
            str(item.get("quantity", 0)),
            _format_price(item.get("unit_price", 0)),
            _format_price(item.get("total", 0)),
        ])

    items_table = Table(
        table_data,
        colWidths=[30, 200, 50, 90, 90],
    )
    items_table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGNMENT", (0, 0), (-1, 0), "CENTER"),
        # Body
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGNMENT", (0, 1), (0, -1), "CENTER"),
        ("ALIGNMENT", (2, 1), (2, -1), "CENTER"),
        ("ALIGNMENT", (3, 1), (-1, -1), "RIGHT"),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.white, colors.HexColor("#f8f8f8")
        ]),
        # Padding
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 15))

    # ── Totals ───────────────────────────────────────────────────────────
    subtotal = invoice_data.get("subtotal", 0)
    fee_amount = invoice_data.get("success_fee_amount", 0)
    fee_config = invoice_data.get("success_fee", {})
    fee_pct = fee_config.get("applied_percent", 3.0)
    grand_total = invoice_data.get("grand_total", 0)

    totals_data = [
        ["Подитог:", _format_price(subtotal)],
        [f"Комиссия RetailPool ({fee_pct}%):", _format_price(fee_amount)],
        ["ИТОГО к оплате:", _format_price(grand_total)],
    ]

    totals_table = Table(totals_data, colWidths=[350, 110])
    totals_table.setStyle(TableStyle([
        ("ALIGNMENT", (0, 0), (0, -1), "RIGHT"),
        ("ALIGNMENT", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#1a1a2e")),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#1a1a2e")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 30))

    # ── Payment details ──────────────────────────────────────────────────
    payment = invoice_data.get("payment_details", {})
    elements.append(Paragraph(
        "<b>Реквизиты для оплаты</b>",
        ParagraphStyle("PaymentHeader", parent=styles["Normal"], fontSize=12,
                       textColor=colors.HexColor("#1a1a2e"), spaceAfter=8),
    ))

    payment_data = [
        ["Получатель:", payment.get("recipient_name", "RetailPool AI")],
        ["Назначение:", payment.get("payment_purpose", "Оплата совместной закупки")],
    ]

    iin = payment.get("recipient_iin", "")
    if iin:
        payment_data.append(["ИИН/БИН:", iin])

    kaspi_num = payment.get("kaspi_gold_number", "")
    if kaspi_num:
        payment_data.append(["Kaspi Gold:", kaspi_num])

    payment_table = Table(payment_data, colWidths=[120, 340])
    payment_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#555555")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(payment_table)
    elements.append(Spacer(1, 30))

    # ── Footer ───────────────────────────────────────────────────────────
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#999999"),
        alignment=TA_CENTER,
    )
    elements.append(Paragraph(
        "Документ сгенерирован автоматически системой RetailPool AI.<br/>"
        "Для вопросов обращайтесь в поддержку.",
        footer_style,
    ))

    # Build PDF
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    logger.info("PDF invoice generated: %s (%d bytes)", inv_number, len(pdf_bytes))
    return pdf_bytes
