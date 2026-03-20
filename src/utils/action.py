from math import pow

from config.config import (
    CONTENT_LENGTH_WEIGHT_MAX,
    CONTENT_LENGTH_WEIGHT_MIN,
    CONTENT_LENGTH_WEIGHT_TARGET_WORDS,
    RECENCY_WEIGHT_FLOOR,
    RECENCY_WEIGHT_HALF_LIFE_HOURS,
)
from config.constants import NEGATIVE, NEUTRAL, POSITIVE


def normalize(action: str, score: float) -> float:
    if action == POSITIVE:
        return score / 2 + 0.5
    return (1 - score) / 2


def get_recency_weight(age_seconds: float | int | None) -> float:
    if age_seconds is None:
        return 1.0

    if RECENCY_WEIGHT_HALF_LIFE_HOURS <= 0:
        return 1.0

    normalized_age_seconds = max(float(age_seconds), 0.0)
    half_life_seconds = RECENCY_WEIGHT_HALF_LIFE_HOURS * 3600
    decay = pow(0.5, normalized_age_seconds / half_life_seconds)
    return RECENCY_WEIGHT_FLOOR + (1 - RECENCY_WEIGHT_FLOOR) * decay


def get_content_length_weight(
    content_length_words: float | int | None,
) -> float:
    if content_length_words is None:
        return 1.0

    if CONTENT_LENGTH_WEIGHT_TARGET_WORDS <= 0:
        return 1.0

    normalized_content_length = max(float(content_length_words), 0.0)
    progress = min(
        normalized_content_length / CONTENT_LENGTH_WEIGHT_TARGET_WORDS,
        1.0,
    )
    return (
        CONTENT_LENGTH_WEIGHT_MIN
        + (CONTENT_LENGTH_WEIGHT_MAX - CONTENT_LENGTH_WEIGHT_MIN) * progress
    )


def get_article_weight(item: dict) -> float:
    return get_recency_weight(item.get("age_seconds")) * (
        get_content_length_weight(item.get("content_length_words"))
    )


def get_recommended_action(
    sentiment_scores_of_news: list[dict],
) -> tuple[str, float]:
    total_weight = 0.0
    action = ""
    action_column_score, correspond_column_score = 0.0, 0.0
    positive_weight, negative_weight = 0.0, 0.0
    for item in sentiment_scores_of_news:
        sentiment_label = item["label"]
        if sentiment_label == NEUTRAL:
            continue

        article_weight = get_article_weight(item)
        total_weight += article_weight
        if sentiment_label == POSITIVE:
            positive_weight += article_weight
        elif sentiment_label == NEGATIVE:
            negative_weight += article_weight

    if positive_weight >= negative_weight:
        action = POSITIVE
    else:
        action = NEGATIVE

    for item in sentiment_scores_of_news:
        sentiment_label = item["label"]
        highest_sentiment_score = item["highest_score"]
        corresponding_sentiment_score = item["corresponding_score"]
        if sentiment_label == NEUTRAL:
            continue

        article_weight = get_article_weight(item)
        if sentiment_label == POSITIVE:
            if action == POSITIVE:
                action_column_score += article_weight * highest_sentiment_score
                correspond_column_score -= (
                    article_weight * corresponding_sentiment_score
                )
            else:
                action_column_score -= article_weight * highest_sentiment_score
                correspond_column_score += (
                    article_weight * corresponding_sentiment_score
                )
        if sentiment_label == NEGATIVE:
            if action == NEGATIVE:
                action_column_score += article_weight * highest_sentiment_score
                correspond_column_score -= (
                    article_weight * corresponding_sentiment_score
                )
            else:
                action_column_score -= article_weight * highest_sentiment_score
                correspond_column_score += (
                    article_weight * corresponding_sentiment_score
                )

    if action == POSITIVE:
        correspond_column_score = -correspond_column_score
    else:
        action_column_score = -action_column_score

    if total_weight:
        action_column_score /= total_weight
        correspond_column_score /= total_weight

    # Signs not clear enough
    if 0 <= action_column_score - correspond_column_score <= 0.2:
        return "Hold", 0.0

    if action_column_score > correspond_column_score:
        return "Buy", normalize(action, action_column_score)
    else:
        return "Sell", normalize(action, correspond_column_score)
