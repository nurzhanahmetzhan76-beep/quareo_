"""
Niche Analyzer — scores categories by monopolization index
and visual weakness of top product cards.

Heuristic v1.0 (Team Lead note):
  - photo < 3          → weak
  - description < 100  → weak
  - rating < 4.0       → weak
  - reviews < 10       → weak
  - no infographics    → weak
  If >50% of top-10 cards are weak → niche is "Vulnerable"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from retailpool.schemas.product import ProductCard

logger = logging.getLogger(__name__)


@dataclass
class CardScore:
    """Visual quality score for a single product card."""
    kaspi_id: str
    weak_signals: int       # count of weakness indicators
    total_signals: int      # total checked indicators
    is_weak: bool


@dataclass
class NicheResult:
    """Aggregated niche analysis result."""
    category_slug: str
    demand_score: float
    seller_count: int
    monopolization_index: float
    weak_card_count: int
    total_cards_checked: int
    vulnerability_ratio: float
    is_vulnerable: bool
    card_scores: list[CardScore]


class NicheAnalyzer:
    """
    Analyzes scraped product data to find vulnerable niches.

    Two axes of analysis:
    1. Monopolization — high demand with few active sellers
    2. Visual weakness — poor card quality in the top results
    """

    # Thresholds for weakness detection (v1.0 heuristic)
    MIN_PHOTOS: int = 3
    MIN_DESC_LENGTH: int = 100
    MIN_RATING: float = 4.0
    MIN_REVIEWS: int = 10
    VULNERABILITY_THRESHOLD: float = 0.5  # >50% weak = vulnerable

    def score_card(self, card: ProductCard) -> CardScore:
        """Score a single product card for visual weakness."""
        signals_total = 5
        weak = 0

        if card.photo_count < self.MIN_PHOTOS:
            weak += 1
        if card.description_length < self.MIN_DESC_LENGTH:
            weak += 1
        if not card.has_infographics:
            weak += 1
        if card.rating is not None and card.rating < self.MIN_RATING:
            weak += 1
        elif card.rating is None:
            weak += 1  # no rating = likely new / untested
        if card.review_count < self.MIN_REVIEWS:
            weak += 1

        return CardScore(
            kaspi_id=card.kaspi_id,
            weak_signals=weak,
            total_signals=signals_total,
            is_weak=weak >= 3,  # 3+ out of 5 = weak card
        )

    def calculate_monopolization(
        self, demand_score: float, seller_count: int
    ) -> float:
        """
        Monopolization index = demand / sellers.
        Higher value = fewer sellers for given demand = opportunity.
        """
        if seller_count <= 0:
            return demand_score * 10  # no sellers = extreme opportunity
        return demand_score / seller_count

    def analyze_niche(
        self,
        category_slug: str,
        products: list[ProductCard],
        seller_count: int,
        top_n: int = 10,
    ) -> NicheResult:
        """
        Full niche analysis for a category.

        Args:
            category_slug: Category identifier.
            products: Scraped product cards from the category.
            seller_count: Number of unique sellers.
            top_n: How many top products to analyze for weakness.
        """
        top_products = products[:top_n]

        # Demand proxy: sum of review counts (correlates with purchase volume)
        demand_score = sum(p.review_count for p in products)

        mono_index = self.calculate_monopolization(demand_score, seller_count)

        # Score each card
        card_scores = [self.score_card(p) for p in top_products]
        weak_count = sum(1 for cs in card_scores if cs.is_weak)
        total_checked = len(card_scores)

        vuln_ratio = weak_count / total_checked if total_checked > 0 else 0.0
        is_vulnerable = vuln_ratio >= self.VULNERABILITY_THRESHOLD

        result = NicheResult(
            category_slug=category_slug,
            demand_score=demand_score,
            seller_count=seller_count,
            monopolization_index=mono_index,
            weak_card_count=weak_count,
            total_cards_checked=total_checked,
            vulnerability_ratio=vuln_ratio,
            is_vulnerable=is_vulnerable,
            card_scores=card_scores,
        )

        logger.info(
            "Niche %s: mono=%.2f, vuln_ratio=%.0f%%, vulnerable=%s",
            category_slug, mono_index, vuln_ratio * 100, is_vulnerable,
        )
        return result
