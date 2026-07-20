"""
AutoReply Router — AI-powered auto-reply for Kaspi seller questions.

The Chrome Extension sends customer questions here; the server generates
a polite, context-aware reply using Gemini (Google AI) and returns it.
Past Q&A pairs are stored so the model can learn the seller's tone.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.database import get_db
from retailpool.models.user import User
from retailpool.models.autoreply import AutoReplySettings, AutoReplyHistory
from retailpool.services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/autoreply", tags=["AutoReply"])


# ── Pydantic schemas ─────────────────────────────────────────────────────

class QuestionIn(BaseModel):
    """Incoming question from the Chrome Extension."""
    question: str
    product_name: str | None = None
    customer_name: str | None = None
    question_id: str | None = None  # Kaspi-side ID to avoid duplicates


class ReplyOut(BaseModel):
    """AI-generated reply."""
    reply: str
    question_id: str | None = None
    confidence: float = 0.9


class QAHistoryItem(BaseModel):
    question: str
    answer: str
    product_name: str | None = None
    created_at: str


class SettingsIn(BaseModel):
    """Seller's auto-reply preferences."""
    tone: str = "friendly"           # friendly / formal / casual
    auto_send: bool = False          # auto-send or require confirmation
    language: str = "ru"             # ru / kz
    store_description: str = ""      # brief store/product description
    custom_instructions: str = ""    # extra instructions for AI


class SettingsOut(SettingsIn):
    pass


class ManualQAIn(BaseModel):
    """Schema for manually adding a Q&A pair to history."""
    question: str
    answer: str
    product_name: str | None = None


# ── DB helpers ────────────────────────────────────────────────────────────

async def _get_settings(user_id: uuid.UUID, db: AsyncSession) -> dict:
    """Load settings from DB, return defaults if not yet saved."""
    result = await db.execute(
        select(AutoReplySettings).where(AutoReplySettings.user_id == user_id)
    )
    row = result.scalars().first()
    if row:
        return {
            "tone": row.tone,
            "auto_send": row.auto_send,
            "language": row.language,
            "store_description": row.store_description,
            "custom_instructions": row.custom_instructions,
        }
    return {
        "tone": "friendly",
        "auto_send": False,
        "language": "ru",
        "store_description": "",
        "custom_instructions": "",
    }


async def _save_settings(user_id: uuid.UUID, data: dict, db: AsyncSession):
    """Upsert settings for a user."""
    result = await db.execute(
        select(AutoReplySettings).where(AutoReplySettings.user_id == user_id)
    )
    row = result.scalars().first()
    if row:
        row.tone = data.get("tone", row.tone)
        row.auto_send = data.get("auto_send", row.auto_send)
        row.language = data.get("language", row.language)
        row.store_description = data.get("store_description", row.store_description)
        row.custom_instructions = data.get("custom_instructions", row.custom_instructions)
    else:
        row = AutoReplySettings(
            user_id=user_id,
            tone=data.get("tone", "friendly"),
            auto_send=data.get("auto_send", False),
            language=data.get("language", "ru"),
            store_description=data.get("store_description", ""),
            custom_instructions=data.get("custom_instructions", ""),
        )
        db.add(row)


async def _save_qa(user_id: uuid.UUID, question: str, answer: str,
                   product_name: str | None, question_id: str | None,
                   db: AsyncSession):
    """Store a Q&A pair in the database."""
    entry = AutoReplyHistory(
        user_id=user_id,
        question=question,
        answer=answer,
        product_name=product_name,
        question_id=question_id,
    )
    db.add(entry)

    # Keep last 200 entries per user — prune old ones
    count_result = await db.execute(
        select(func.count(AutoReplyHistory.id)).where(
            AutoReplyHistory.user_id == user_id
        )
    )
    total = count_result.scalar() or 0
    if total > 200:
        # Find IDs to delete (oldest entries beyond 200)
        oldest = await db.execute(
            select(AutoReplyHistory.id)
            .where(AutoReplyHistory.user_id == user_id)
            .order_by(AutoReplyHistory.created_at.asc())
            .limit(total - 200)
        )
        old_ids = [row[0] for row in oldest.all()]
        if old_ids:
            from sqlalchemy import delete
            await db.execute(
                delete(AutoReplyHistory).where(AutoReplyHistory.id.in_(old_ids))
            )


async def _get_history(user_id: uuid.UUID, db: AsyncSession,
                       limit: int = 50) -> list[dict]:
    """Get recent Q&A history for a user."""
    result = await db.execute(
        select(AutoReplyHistory)
        .where(AutoReplyHistory.user_id == user_id)
        .order_by(AutoReplyHistory.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    # Return in chronological order (oldest first) for prompt building
    rows.reverse()
    return [
        {
            "question": r.question,
            "answer": r.answer,
            "product_name": r.product_name,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


# ── AI reply generation ──────────────────────────────────────────────────

def _build_prompt(question: str, product_name: str | None,
                  customer_name: str | None, settings: dict,
                  history: list[dict]) -> str:
    """Build a system + user prompt for the AI model."""

    tone_map = {
        "friendly": "дружелюбный, тёплый, с лёгким неформальным стилем",
        "formal": "вежливый, профессиональный, деловой стиль",
        "casual": "разговорный, простой, как друг с другом",
    }
    tone_desc = tone_map.get(settings.get("tone", "friendly"), tone_map["friendly"])
    lang = "казахском" if settings.get("language") == "kz" else "русском"

    # Last 15 Q&A pairs for context
    recent = history[-15:] if history else []
    history_block = ""
    if recent:
        history_block = "\n\nПримеры ПРОШЛЫХ ответов продавца (ориентируйся на их стиль):\n"
        for qa in recent:
            history_block += f"  Вопрос: {qa['question']}\n  Ответ: {qa['answer']}\n\n"

    store_desc = settings.get("store_description", "")
    custom = settings.get("custom_instructions", "")

    prompt = f"""Ты — ИИ-помощник продавца на маркетплейсе Kaspi.kz.
Твоя задача — ответить на вопрос покупателя от имени продавца.

ПРАВИЛА:
1. Отвечай на {lang} языке.
2. Тон: {tone_desc}.
3. НИКОГДА не груби, не будь саркастичным, не показывай раздражение.
4. Отвечай коротко и по делу (1-3 предложения).
5. Если не знаешь точного ответа — вежливо предложи связаться по телефону или в чате для уточнения.
6. Не выдумывай технические характеристики товара — лучше скажи "уточню и отвечу".
7. Каждый ответ должен быть немного уникальным, НЕ используй одну и ту же шаблонную фразу.
8. Можно использовать эмодзи, но умеренно (1-2 максимум).
"""

    if store_desc:
        prompt += f"\nОписание магазина: {store_desc}\n"
    if custom:
        prompt += f"\nДополнительные инструкции от продавца: {custom}\n"

    prompt += history_block

    if product_name:
        prompt += f"\nТовар, к которому задан вопрос: {product_name}\n"
    if customer_name:
        prompt += f"Имя покупателя: {customer_name}\n"

    prompt += f"\nВОПРОС ПОКУПАТЕЛЯ: {question}\n\nТвой ответ (только текст ответа, без кавычек и пояснений):"

    return prompt


async def _generate_reply_ai(prompt: str) -> str:
    """Call Groq API (Llama-3) to generate a reply."""
    import httpx

    from retailpool.config import settings as app_settings
    api_key = app_settings.GROQ_API_KEY
    if not api_key:
        # Fallback: generate a template reply
        return _generate_fallback_reply()

    url = "https://api.groq.com/openai/v1/chat/completions"

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 256,
        "top_p": 0.9,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                logger.error("Groq API error %s: %s", resp.status_code, resp.text[:500])
                return _generate_fallback_reply()

            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return text.strip().strip('"').strip("'")
    except Exception as e:
        logger.error("Groq API exception: %s", e)
        return _generate_fallback_reply()


def _generate_fallback_reply() -> str:
    """Fallback when AI is unavailable."""
    import random
    replies = [
        "Здравствуйте! Спасибо за вопрос. Уточню информацию и свяжусь с вами в ближайшее время 🙏",
        "Добрый день! Благодарю за интерес к товару. Позвольте уточнить детали — ответим в кратчайшие сроки.",
        "Здравствуйте! Хороший вопрос. Я сейчас уточню и обязательно вернусь с ответом 😊",
    ]
    return random.choice(replies)


# ── API Endpoints ────────────────────────────────────────────────────────

@router.post("/generate", response_model=ReplyOut)
async def generate_reply(
    data: QuestionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate an AI reply for a customer question."""
    user_id = user.id
    settings = await _get_settings(user_id, db)
    history = await _get_history(user_id, db, limit=15)

    prompt = _build_prompt(
        question=data.question,
        product_name=data.product_name,
        customer_name=data.customer_name,
        settings=settings,
        history=history,
    )

    reply_text = await _generate_reply_ai(prompt)

    # Save to history in DB
    await _save_qa(user_id, data.question, reply_text,
                   data.product_name, data.question_id, db)

    return ReplyOut(
        reply=reply_text,
        question_id=data.question_id,
    )


@router.get("/settings", response_model=SettingsOut)
async def get_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get auto-reply settings."""
    return SettingsOut(**await _get_settings(user.id, db))


@router.post("/settings", response_model=SettingsOut)
async def save_settings(
    data: SettingsIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save auto-reply settings."""
    await _save_settings(user.id, data.model_dump(), db)
    return SettingsOut(**data.model_dump())


@router.get("/history", response_model=list[QAHistoryItem])
async def get_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get Q&A history for this seller."""
    items = await _get_history(user.id, db, limit=50)
    return [QAHistoryItem(**item) for item in items]


@router.post("/history/add")
async def add_manual_qa(
    data: ManualQAIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually add a Q&A pair (for importing past answers to train AI style)."""
    await _save_qa(
        user_id=user.id,
        question=data.question,
        answer=data.answer,
        product_name=data.product_name,
        question_id=None,
        db=db,
    )
    return {"status": "ok", "message": "Q&A pair saved successfully"}
