from datetime import datetime, timedelta
from multiprocessing import Pool

from flask import Flask, render_template, request

from config.config import CPU_COUNT, MAX_NEWS_LOOKBACK_DAYS, TIMESTAMP_FORMAT
from scrapers import yahoo_news_scraper
from utils import action, data, sentiment_analyzer, time


def calculate_paragraph_score(news_item, current_timestamp):
    paragraphs_with_sentiment_scores = []
    paragraphs, article_status = yahoo_news_scraper.get_news_paragraphs(
        news_item["news_URL"]
    )

    news = {}

    current_time_seconds = time.convert_timestamp_to_seconds(
        TIMESTAMP_FORMAT, current_timestamp
    )
    publish_time_seconds = time.convert_timestamp_to_seconds(
        TIMESTAMP_FORMAT, news_item["publish_date"]
    )

    sentiment_scores_of_new = {}
    if current_time_seconds and publish_time_seconds:
        how_long_ago = time.format_time_difference(
            current_time_seconds - publish_time_seconds
        )
        news["how_long_ago"] = how_long_ago

    if not paragraphs:
        news["paragraphs"] = []
        news["article_status"] = article_status or "unavailable"
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
    }

    return (news, sentiment_scores_of_new)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def home():
        return render_template(
            "index.html", max_news_lookback_days=MAX_NEWS_LOOKBACK_DAYS
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

        company_exists, [company_name, ticker_symbol] = (
            data.check_company_exists(input_company)
        )
        if company_exists:
            current_timestamp = (
                datetime.now() - timedelta(days=start_day)
            ).strftime(TIMESTAMP_FORMAT)
            start_timestamp = (
                datetime.now() - timedelta(days=end_day)
            ).strftime(TIMESTAMP_FORMAT)

            news = yahoo_news_scraper.get_news_URLs(
                ticker_symbol,
                start_timestamp=start_timestamp,
                end_timestamp=current_timestamp,
                title_flag=True,
            )

            sentiment_scores_of_news = []  # Including the label, the highest sentiment score, and the corresponding label's score

            if news:
                args = []
                results = []
                for news_item in news:
                    args.append((news_item, current_timestamp))

                sentiment_analyzer.preload_model()
                with Pool(CPU_COUNT) as pool:
                    results = pool.starmap(calculate_paragraph_score, args)

                for news_item, result in zip(news, results, strict=True):
                    result_news, sentiment_scores_of_new = result
                    news_item.update(result_news)
                    if sentiment_scores_of_new:
                        sentiment_scores_of_news.append(sentiment_scores_of_new)

            # Recommended action
            recommended_action, confidence_index = (
                action.get_recommended_action(sentiment_scores_of_news)
            )

            return render_template(
                "index.html",
                company_exists=company_exists,
                company_name=company_name,
                ticker_symbol=ticker_symbol,
                news=news,
                recommended_action=recommended_action,
                confidence_index=f"{confidence_index: .3f}",
                max_news_lookback_days=MAX_NEWS_LOOKBACK_DAYS,
                start_day=start_day,
                end_day=end_day,
            )
        else:
            return render_template(
                "index.html",
                company_exists=company_exists,
                message="No such company exists",
                max_news_lookback_days=MAX_NEWS_LOOKBACK_DAYS,
            )

    return app
