"""
Tests for Niche Analyzer and Document Service (unit tests, no DB needed).
"""

import pytest
from decimal import Decimal

from retailpool.schemas.product import ProductCard
from retailpool.scraper.niche_analyzer import NicheAnalyzer

import uuid
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════════════════
# Niche Analyzer Tests
# ═══════════════════════════════════════════════════════════════════════════

def _make_card(
    photo_count: int = 1,
    desc_len: int = 50,
    has_infographics: bool = False,
    rating: float | None = 3.5,
    review_count: int = 5,
) -> ProductCard:
    return ProductCard(
        kaspi_id=f"test-{uuid.uuid4().hex[:6]}",
        title="Test Product",
        category_slug="test",
        url="https://kaspi.kz/shop/p/test/",
        photo_count=photo_count,
        has_infographics=has_infographics,
        description_length=desc_len,
        rating=rating,
        review_count=review_count,
    )


class TestNicheAnalyzer:

    def test_weak_card_detection(self):
        """Card with few photos, short desc, no infographics = weak."""
        analyzer = NicheAnalyzer()
        card = _make_card(photo_count=1, desc_len=30, rating=3.0, review_count=2)
        score = analyzer.score_card(card)
        assert score.is_weak is True
        assert score.weak_signals >= 3

    def test_strong_card_detection(self):
        """Card with good metrics should NOT be weak."""
        analyzer = NicheAnalyzer()
        card = _make_card(
            photo_count=8, desc_len=500, has_infographics=True,
            rating=4.7, review_count=200,
        )
        score = analyzer.score_card(card)
        assert score.is_weak is False
        assert score.weak_signals <= 2

    def test_vulnerable_niche(self):
        """Niche with >50% weak cards should be marked vulnerable."""
        analyzer = NicheAnalyzer()
        # 8 weak + 2 strong = 80% weak
        products = [_make_card() for _ in range(8)] + [
            _make_card(photo_count=10, desc_len=500, has_infographics=True,
                       rating=4.8, review_count=300)
            for _ in range(2)
        ]
        result = analyzer.analyze_niche("test-cat", products, seller_count=3)
        assert result.is_vulnerable is True
        assert result.vulnerability_ratio >= 0.5

    def test_non_vulnerable_niche(self):
        """Niche with strong cards should NOT be vulnerable."""
        analyzer = NicheAnalyzer()
        products = [
            _make_card(photo_count=6, desc_len=300, has_infographics=True,
                       rating=4.5, review_count=100)
            for _ in range(10)
        ]
        result = analyzer.analyze_niche("strong-cat", products, seller_count=20)
        assert result.is_vulnerable is False

    def test_monopolization_index(self):
        """High demand + few sellers = high monopolization."""
        analyzer = NicheAnalyzer()
        assert analyzer.calculate_monopolization(1000, 2) == 500.0
        assert analyzer.calculate_monopolization(1000, 100) == 10.0
        # Zero sellers = extreme opportunity
        assert analyzer.calculate_monopolization(100, 0) == 1000.0



