import json
from datetime import datetime, timedelta
from multiprocessing import Pool
from urllib.parse import urlencode

from flask import Flask, redirect, render_template, request

from config.config import (
    CPU_COUNT,
    MAX_NEWS_LOOKBACK_DAYS,
    NEWS_ARTICLE_CACHE_RETENTION_SECONDS,
    NEWS_LIST_CACHE_RETENTION_SECONDS,
    OFFLINE_MODE,
    SENTIMENT_CACHE_RETENTION_SECONDS,
    SENTIMENT_CACHE_TTL_SECONDS,
    TIMESTAMP_FORMAT,
)
from scrapers import yahoo_news_scraper
from utils import action, cache, data, sentiment_analyzer, time

CACHE_NAMESPACES = ("news_urls", "news_articles", "news_sentiment")


def _get_sentiment_cache_key(news_url: str) -> str:
    return json.dumps(
        {
            "news_url": news_url,
            "model": sentiment_analyzer.get_model_cache_identity(),
        },
        sort_keys=True,
    )


def _get_float_form_value(
    form_data,
    key: str,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    try:
        value = float(form_data[key]) if form_data[key] else default
    except (ValueError, KeyError):
        value = default

    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _get_int_form_value(
    form_data,
    key: str,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    try:
        value = int(form_data[key]) if form_data[key] else default
    except (ValueError, KeyError):
        value = default

    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _get_weight_config_from_form(form_data=None) -> dict:
    form_data = form_data or {}
    content_length_min = _get_float_form_value(
        form_data,
        "content_length_min",
        action.CONTENT_LENGTH_WEIGHT_MIN,
        minimum=0.0,
        maximum=3.0,
    )
    return action.get_weight_config(
        {
            "recency_half_life_hours": _get_float_form_value(
                form_data,
                "recency_half_life_hours",
                action.RECENCY_WEIGHT_HALF_LIFE_HOURS,
                minimum=0.0,
                maximum=720.0,
            ),
            "recency_floor": _get_float_form_value(
                form_data,
                "recency_floor",
                action.RECENCY_WEIGHT_FLOOR,
                minimum=0.0,
                maximum=1.0,
            ),
            "content_length_target_words": _get_int_form_value(
                form_data,
                "content_length_target_words",
                action.CONTENT_LENGTH_WEIGHT_TARGET_WORDS,
                minimum=0,
                maximum=2000,
            ),
            "content_length_min": content_length_min,
            "content_length_max": _get_float_form_value(
                form_data,
                "content_length_max",
                action.CONTENT_LENGTH_WEIGHT_MAX,
                minimum=content_length_min,
                maximum=3.0,
            ),
        }
    )


def _get_content_length_words(paragraphs) -> int | None:
    if not paragraphs:
        return None

    content_length_words = 0
    for paragraph in paragraphs:
        content = paragraph
        if isinstance(paragraph, dict):
            content = paragraph.get("content", "")

        normalized_content = str(content).strip()
        if normalized_content:
            content_length_words += len(normalized_content.split())

    return content_length_words


def _get_cached_content_length_words(
    cached_sentiment: dict | None,
) -> int | None:
    if not cached_sentiment:
        return None

    return _get_content_length_words(
        cached_sentiment.get("article_paragraphs")
        or cached_sentiment.get("paragraphs")
    )


def calculate_paragraph_score(
    news_item,
    current_timestamp,
    age_reference_timestamp=None,
    model_available=True,
):
    def _build_sentiment_summary(
        sentiment_scores: dict,
        content_length_words: int | None = None,
    ) -> dict:
        if not sentiment_scores:
            return {}

        summary = dict(sentiment_scores)
        if age_seconds is not None:
            summary["age_seconds"] = age_seconds
        if content_length_words is not None:
            summary["content_length_words"] = content_length_words
        return summary

    paragraphs_with_sentiment_scores = []
    cache_key = _get_sentiment_cache_key(news_item["news_URL"])
    cached_sentiment = cache.get_cached_json(
        "news_sentiment", cache_key, SENTIMENT_CACHE_TTL_SECONDS
    )
    stale_cached_sentiment = cache.get_cached_json(
        "news_sentiment",
        cache_key,
        SENTIMENT_CACHE_TTL_SECONDS,
        allow_stale=True,
    )
    paragraphs, article_status = yahoo_news_scraper.get_news_paragraphs(
        news_item["news_URL"]
    )

    news = {}

    age_reference_seconds = time.convert_timestamp_to_seconds(
        TIMESTAMP_FORMAT, age_reference_timestamp or current_timestamp
    )
    publish_time_seconds = time.convert_timestamp_to_seconds(
        TIMESTAMP_FORMAT, news_item["publish_date"]
    )

    age_seconds = None
    sentiment_scores_of_new = {}
    if age_reference_seconds and publish_time_seconds:
        age_seconds = max(age_reference_seconds - publish_time_seconds, 0)
        how_long_ago = time.format_time_difference(age_seconds)
        news["how_long_ago"] = how_long_ago

    if not paragraphs:
        if stale_cached_sentiment is not None and article_status != "premium":
            news["paragraphs"] = stale_cached_sentiment.get("paragraphs", [])
            news["overall_sentiment_score"] = stale_cached_sentiment.get(
                "overall_sentiment_score", {}
            )
            return (
                news,
                _build_sentiment_summary(
                    stale_cached_sentiment.get("sentiment_scores_of_new", {}),
                    _get_cached_content_length_words(stale_cached_sentiment),
                ),
            )

        news["paragraphs"] = []
        news["article_status"] = article_status or "unavailable"
        return (news, sentiment_scores_of_new)

    reusable_cached_sentiment = None
    for cached_value in (cached_sentiment, stale_cached_sentiment):
        if (
            cached_value is not None
            and cached_value.get("article_paragraphs") == paragraphs
        ):
            reusable_cached_sentiment = cached_value
            break

    if reusable_cached_sentiment is not None:
        news["paragraphs"] = reusable_cached_sentiment.get("paragraphs", [])
        news["overall_sentiment_score"] = reusable_cached_sentiment.get(
            "overall_sentiment_score", {}
        )
        return (
            news,
            _build_sentiment_summary(
                reusable_cached_sentiment.get("sentiment_scores_of_new", {}),
                _get_cached_content_length_words(reusable_cached_sentiment),
            ),
        )

    if not model_available:
        news["paragraphs"] = []
        news["article_status"] = "model_unavailable"
        return (news, sentiment_scores_of_new)

    for paragraph in paragraphs:
        negative_score, neutral_score, positive_score = (
            sentiment_analyzer.get_sentiment_score(paragraph)
        )
        paragraphs_with_sentiment_scores.append(
            {
                "content": paragraph,
                "positive_score": f"{positive_score: .3f}",
                "neutral_score": f"{neutral_score: .3f}",
                "negative_score": f"{negative_score: .3f}",
            }
        )

    news["paragraphs"] = paragraphs_with_sentiment_scores
    content_length_words = _get_content_length_words(paragraphs)

    # News overall sentiment score
    (
        sentiment_label,
        highest_sentiment_score,
        corresponding_sentiment_score,
    ) = sentiment_analyzer.get_overall_sentiment_score(
        paragraphs_with_sentiment_scores
    )

    news["overall_sentiment_score"] = {
        "label": sentiment_label,
        "score": f"{highest_sentiment_score: .3f}",
    }
    sentiment_scores_of_new = {
        "label": sentiment_label,
        "highest_score": highest_sentiment_score,
        "corresponding_score": corresponding_sentiment_score,
        "content_length_words": content_length_words,
    }
    cache.set_cached_json(
        "news_sentiment",
        cache_key,
        {
            "article_paragraphs": paragraphs,
            "paragraphs": paragraphs_with_sentiment_scores,
            "overall_sentiment_score": news["overall_sentiment_score"],
            "sentiment_scores_of_new": sentiment_scores_of_new,
        },
    )

    return (
        news,
        _build_sentiment_summary(
            sentiment_scores_of_new,
            content_length_words,
        ),
    )


def _render_index(**context):
    default_context = {
        "max_news_lookback_days": MAX_NEWS_LOOKBACK_DAYS,
        "offline_mode": OFFLINE_MODE,
        "search_value": "",
        "start_day": 0,
        "end_day": 2,
        "weight_config": _get_weight_config_from_form(),
        "recommendation_inputs": [],
        "message_level": "info",
    }
    default_context.update(context)
    return render_template("index.html", **default_context)


def _redirect_home_with_message(message: str, message_level: str = "info"):
    query_string = urlencode(
        {"message": message, "message_level": message_level}
    )
    return redirect(f"/?{query_string}")


def create_app() -> Flask:
    app = Flask(__name__)
    cache.cleanup_expired_json(
        {
            CACHE_NAMESPACES[0]: NEWS_LIST_CACHE_RETENTION_SECONDS,
            CACHE_NAMESPACES[1]: NEWS_ARTICLE_CACHE_RETENTION_SECONDS,
            CACHE_NAMESPACES[2]: SENTIMENT_CACHE_RETENTION_SECONDS,
        }
    )

    @app.route("/")
    def home():
        message_level = request.args.get("message_level", "info")
        if message_level not in {"info", "error"}:
            message_level = "info"

        return _render_index(
            message=request.args.get("message"),
            message_level=message_level,
        )

    @app.route("/api/company-suggestions")
    def company_suggestions():
        query = request.args.get("q", "")
        return {"suggestions": data.get_company_suggestions(query)}

    @app.route("/clear-cache", methods=["POST"])
    def clear_cache():
        if cache.clear_cache_namespaces(CACHE_NAMESPACES):
            return _redirect_home_with_message(
                message=(
                    "Cache cleared. Cached news, article bodies, and "
                    "sentiment results were removed."
                )
            )

        return _redirect_home_with_message(
            message=(
                "Cache could not be cleared. Check filesystem permissions "
                "for the configured cache directory."
            ),
            message_level="error",
        )

    @app.route("/", methods=["POST"])
    def search():
        input_company = request.form["company"]

        # Handle empty start/end values with defaults
        try:
            start_day = (
                int(request.form["start"]) if request.form["start"] else 0
            )
        except (ValueError, KeyError):
            start_day = 0

        try:
            end_day = int(request.form["end"]) if request.form["end"] else 2
        except (ValueError, KeyError):
            end_day = 2

        weight_config = _get_weight_config_from_form(request.form)

        company_exists, [company_name, ticker_symbol] = (
            data.check_company_exists(input_company)
        )
        if company_exists:
            message = None
            now = datetime.now()
            actual_timestamp = now.strftime(TIMESTAMP_FORMAT)
            current_timestamp = (now - timedelta(days=start_day)).strftime(
                TIMESTAMP_FORMAT
            )
            start_timestamp = (now - timedelta(days=end_day)).strftime(
                TIMESTAMP_FORMAT
            )

            news, news_source = yahoo_news_scraper.get_news_URLs(
                ticker_symbol,
                start_timestamp=start_timestamp,
                end_timestamp=current_timestamp,
                title_flag=True,
            )
            if OFFLINE_MODE:
                if news_source == "cache":
                    message = (
                        "Offline mode is enabled. Showing cached news and "
                        "sentiment where available."
                    )
                elif news_source == "stale_cache":
                    message = (
                        "Offline mode is enabled. Showing stale cached news "
                        "and sentiment where available."
                    )
                elif news_source == "offline_unavailable":
                    message = (
                        "Offline mode is enabled, but no cached news was "
                        "found for this company and date range."
                    )
            elif news_source == "stale_cache":
                message = (
                    "Live news fetch failed. Showing stale cached news and "
                    "sentiment where available."
                )
            elif news_source == "offline_unavailable":
                message = (
                    "Live news fetch failed and no cached news was "
                    "available for this company and date range."
                )

            sentiment_scores_of_news = []  # Including the label, the highest sentiment score, and the corresponding label's score

            if news:
                args = []
                results = []
                for news_item in news:
                    args.append(
                        (
                            news_item,
                            current_timestamp,
                            actual_timestamp,
                            True,
                        )
                    )

                model_available = True
                try:
                    sentiment_analyzer.preload_model()
                except Exception:
                    model_available = False
                    if OFFLINE_MODE:
                        extra_message = (
                            "Offline mode is enabled. Cached news is shown "
                            "where available, but uncached articles could "
                            "not be analyzed because no local sentiment "
                            "model was found."
                        )
                        if message:
                            message = f"{message} {extra_message}"
                        else:
                            message = extra_message
                    else:
                        extra_message = (
                            "Live sentiment analysis is unavailable right "
                            "now. Showing cached sentiment where available."
                        )
                        if message:
                            message = f"{message} {extra_message}"
                        else:
                            message = extra_message

                if not model_available:
                    args = [
                        (
                            news_item,
                            current_timestamp,
                            actual_timestamp,
                            False,
                        )
                        for news_item in news
                    ]

                with Pool(CPU_COUNT) as pool:
                    results = pool.starmap(calculate_paragraph_score, args)

                for news_item, result in zip(news, results, strict=True):
                    result_news, sentiment_scores_of_new = result
                    news_item.update(result_news)
                    if sentiment_scores_of_new:
                        sentiment_scores_of_news.append(sentiment_scores_of_new)

            # Recommended action
            recommended_action, confidence_index = (
                action.get_recommended_action(
                    sentiment_scores_of_news,
                    weight_config,
                )
            )

            return _render_index(
                company_exists=company_exists,
                company_name=company_name,
                ticker_symbol=ticker_symbol,
                search_value=f"{company_name} ({ticker_symbol})",
                news=news,
                recommended_action=recommended_action,
                confidence_index=f"{confidence_index: .3f}",
                message=message,
                start_day=start_day,
                end_day=end_day,
                weight_config=weight_config,
                recommendation_inputs=sentiment_scores_of_news,
            )
        else:
            return _render_index(
                company_exists=company_exists,
                search_value=input_company,
                message="No such company exists",
                start_day=start_day,
                end_day=end_day,
                weight_config=weight_config,
                recommendation_inputs=[],
                message_level="error",
            )

    return app
