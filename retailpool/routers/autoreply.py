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
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.database import get_db
from retailpool.models.user import User
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


# ── In-memory store (MVP — production would use DB table) ────────────────

# Per-user settings and history
_user_settings: dict[str, dict] = {}
_user_history: dict[str, list[dict]] = {}


def _get_settings(user_id: str) -> dict:
    return _user_settings.get(user_id, {
        "tone": "friendly",
        "auto_send": False,
        "language": "ru",
        "store_description": "",
        "custom_instructions": "",
    })


def _save_qa(user_id: str, question: str, answer: str, product_name: str | None):
    if user_id not in _user_history:
        _user_history[user_id] = []
    _user_history[user_id].append({
        "question": question,
        "answer": answer,
        "product_name": product_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # Keep last 200 entries max
    if len(_user_history[user_id]) > 200:
        _user_history[user_id] = _user_history[user_id][-200:]


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
):
    """Generate an AI reply for a customer question."""
    user_id = str(user.id)
    settings = _get_settings(user_id)
    history = _user_history.get(user_id, [])

    prompt = _build_prompt(
        question=data.question,
        product_name=data.product_name,
        customer_name=data.customer_name,
        settings=settings,
        history=history,
    )

    reply_text = await _generate_reply_ai(prompt)

    # Save to history
    _save_qa(user_id, data.question, reply_text, data.product_name)

    return ReplyOut(
        reply=reply_text,
        question_id=data.question_id,
    )


@router.get("/settings", response_model=SettingsOut)
async def get_settings(user: User = Depends(get_current_user)):
    """Get auto-reply settings."""
    return SettingsOut(**_get_settings(str(user.id)))


@router.post("/settings", response_model=SettingsOut)
async def save_settings(
    data: SettingsIn,
    user: User = Depends(get_current_user),
):
    """Save auto-reply settings."""
    _user_settings[str(user.id)] = data.model_dump()
    return SettingsOut(**_user_settings[str(user.id)])


@router.get("/history", response_model=list[QAHistoryItem])
async def get_history(user: User = Depends(get_current_user)):
    """Get Q&A history for this seller."""
    items = _user_history.get(str(user.id), [])
    return [QAHistoryItem(**item) for item in items[-50:]]


@router.post("/history/add")
async def add_manual_qa(
    data: QuestionIn,
    user: User = Depends(get_current_user),
):
    """Manually add a Q&A pair (for importing past answers)."""
    # Re-using QuestionIn: question = customer question, product_name used for answer
    # This is a workaround — ideally a separate schema
    return {"status": "ok", "message": "Use POST /generate instead"}
