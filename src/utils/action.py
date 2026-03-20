from math import pow

from config.config import (
    CONTENT_LENGTH_WEIGHT_MAX,
    CONTENT_LENGTH_WEIGHT_MIN,
    CONTENT_LENGTH_WEIGHT_TARGET_WORDS,
    RECENCY_WEIGHT_FLOOR,
    RECENCY_WEIGHT_HALF_LIFE_HOURS,
)
from config.constants import NEGATIVE, NEUTRAL, POSITIVE


def get_weight_config(overrides: dict | None = None) -> dict:
    overrides = overrides or {}
    recency_half_life_hours = max(
        float(
            overrides.get(
                "recency_half_life_hours",
                RECENCY_WEIGHT_HALF_LIFE_HOURS,
            )
        ),
        0.0,
    )
    recency_floor = min(
        max(float(overrides.get("recency_floor", RECENCY_WEIGHT_FLOOR)), 0.0),
        1.0,
    )
    content_length_target_words = max(
        int(
            overrides.get(
                "content_length_target_words",
                CONTENT_LENGTH_WEIGHT_TARGET_WORDS,
            )
        ),
        0,
    )
    content_length_min = max(
        float(
            overrides.get(
                "content_length_min",
                CONTENT_LENGTH_WEIGHT_MIN,
            )
        ),
        0.0,
    )
    content_length_max = max(
        float(
            overrides.get(
                "content_length_max",
                CONTENT_LENGTH_WEIGHT_MAX,
            )
        ),
        content_length_min,
    )
    return {
        "recency_half_life_hours": recency_half_life_hours,
        "recency_floor": recency_floor,
        "content_length_target_words": content_length_target_words,
        "content_length_min": content_length_min,
        "content_length_max": content_length_max,
    }


def normalize(action: str, score: float) -> float:
    if action == POSITIVE:
        return score / 2 + 0.5
    return (1 - score) / 2


def get_recency_weight(
    age_seconds: float | int | None,
    *,
    half_life_hours: float | None = None,
    floor: float | None = None,
) -> float:
    if age_seconds is None:
        return 1.0

    half_life_hours = (
        RECENCY_WEIGHT_HALF_LIFE_HOURS
        if half_life_hours is None
        else max(float(half_life_hours), 0.0)
    )
    floor = (
        RECENCY_WEIGHT_FLOOR
        if floor is None
        else min(max(float(floor), 0.0), 1.0)
    )

    if half_life_hours <= 0:
        return 1.0

    normalized_age_seconds = max(float(age_seconds), 0.0)
    half_life_seconds = half_life_hours * 3600
    decay = pow(0.5, normalized_age_seconds / half_life_seconds)
    return floor + (1 - floor) * decay


def get_content_length_weight(
    content_length_words: float | int | None,
    *,
    target_words: int | None = None,
    min_weight: float | None = None,
    max_weight: float | None = None,
) -> float:
    if content_length_words is None:
        return 1.0

    target_words = (
        CONTENT_LENGTH_WEIGHT_TARGET_WORDS
        if target_words is None
        else max(int(target_words), 0)
    )
    min_weight = (
        CONTENT_LENGTH_WEIGHT_MIN
        if min_weight is None
        else max(float(min_weight), 0.0)
    )
    max_weight = (
        CONTENT_LENGTH_WEIGHT_MAX
        if max_weight is None
        else max(float(max_weight), min_weight)
    )

    if target_words <= 0:
        return 1.0

    normalized_content_length = max(float(content_length_words), 0.0)
    progress = min(
        normalized_content_length / target_words,
        1.0,
    )
    return min_weight + (max_weight - min_weight) * progress


def get_article_weight(item: dict, weight_config: dict | None = None) -> float:
    weight_config = get_weight_config(weight_config)
    return get_recency_weight(
        item.get("age_seconds"),
        half_life_hours=weight_config["recency_half_life_hours"],
        floor=weight_config["recency_floor"],
    ) * (
        get_content_length_weight(
            item.get("content_length_words"),
            target_words=weight_config["content_length_target_words"],
            min_weight=weight_config["content_length_min"],
            max_weight=weight_config["content_length_max"],
        )
    )


def get_recommended_action(
    sentiment_scores_of_news: list[dict],
    weight_config: dict | None = None,
) -> tuple[str, float]:
    weight_config = get_weight_config(weight_config)
    total_weight = 0.0
    action = ""
    action_column_score, correspond_column_score = 0.0, 0.0
    positive_weight, negative_weight = 0.0, 0.0
    for item in sentiment_scores_of_news:
        sentiment_label = item["label"]
        if sentiment_label == NEUTRAL:
            continue

        article_weight = get_article_weight(item, weight_config)
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

        article_weight = get_article_weight(item, weight_config)
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
