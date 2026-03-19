from datetime import datetime, timedelta
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config.config import (
    NEWS_ARTICLE_CACHE_TTL_SECONDS,
    NEWS_LIST_CACHE_TTL_SECONDS,
    TIMESTAMP_FORMAT,
    UTC_DIFFERENCE,
)
from utils import cache, data

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
}

YAHOO_PREMIUM_MARKERS = (
    '"milestone":"premium-premiumnews"',
    '"yhighvalueaction":"premium-premiumnews"',
    '"pl2":"unspecified-block_all"',
)


def _get_news_list_cache_key(
    ticker_symbol: str,
    start_timestamp: str,
    end_timestamp: str,
    title_flag: bool,
) -> str:
    normalized_start = datetime.strptime(
        start_timestamp, TIMESTAMP_FORMAT
    ).date()
    normalized_end = datetime.strptime(end_timestamp, TIMESTAMP_FORMAT).date()

    return (
        f"{ticker_symbol}:{normalized_start.isoformat()}:"
        f"{normalized_end.isoformat()}:{title_flag}"
    )


def get_news_URLs(
    ticker_symbol: str,
    start_timestamp: str,
    end_timestamp: str,
    title_flag: bool = False,
) -> list:
    cache_key = _get_news_list_cache_key(
        ticker_symbol, start_timestamp, end_timestamp, title_flag
    )
    cached_news_urls = cache.get_cached_json(
        "news_urls", cache_key, NEWS_LIST_CACHE_TTL_SECONDS
    )
    if cached_news_urls is not None:
        return cached_news_urls

    API_URL = f"https://finance.yahoo.com/xhr/ncp?location=US&queryRef=newsAll&serviceKey=ncp_fin&listName={ticker_symbol}-news&lang=en-US&region=US"

    news_URLs = []

    uuid = ""

    while True:
        payload = {
            "payload": {
                "gqlVariables": {
                    "tickerStream": {"pagination": {"uuids": uuid}}
                }
            },
            "serviceConfig": {
                "s": [ticker_symbol],
                "snippetCount": 5000,
            },
        }

        response = requests.post(API_URL, json=payload, headers=headers)

        if response.status_code == 200:
            streams = response.json()["data"]["tickerStream"]["stream"]

            if not streams:
                break

            for stream in streams:
                if stream["content"]["clickThroughUrl"]:
                    publish_datetime = datetime.strptime(
                        stream["content"]["pubDate"], TIMESTAMP_FORMAT
                    )
                    shifted_publish_datetime = publish_datetime + timedelta(
                        hours=UTC_DIFFERENCE
                    )
                    shifted_publish_date = shifted_publish_datetime.strftime(
                        TIMESTAMP_FORMAT
                    )

                    start_datetime = datetime.strptime(
                        start_timestamp, TIMESTAMP_FORMAT
                    )
                    end_datetime = datetime.strptime(
                        end_timestamp, TIMESTAMP_FORMAT
                    )

                    if not (
                        start_datetime
                        <= shifted_publish_datetime
                        <= end_datetime
                    ):
                        continue

                    company_name = data.get_company_name_by_ticker(
                        ticker_symbol
                    )
                    news_title = stream["content"]["title"]

                    if (
                        title_flag
                        and company_name.lower() not in news_title.lower()
                        and ticker_symbol.lower() not in news_title.lower()
                    ):
                        continue

                    news_URLs.append(
                        {
                            "publish_date": shifted_publish_date,
                            "news_URL": stream["content"]["clickThroughUrl"][
                                "url"
                            ],
                            "news_title": news_title,
                        }
                    )

            uuid = response.json()["data"]["tickerStream"]["pagination"][
                "uuids"
            ]
        else:
            print(
                f"Failed to retrieve the page. Status code: {response.status_code}"
            )

    sorted_news_URLs = sorted(
        news_URLs,
        key=lambda x: datetime.strptime(x["publish_date"], TIMESTAMP_FORMAT),
        reverse=True,
    )
    cache.set_cached_json("news_urls", cache_key, sorted_news_URLs)
    return sorted_news_URLs


def get_news_paragraphs(news_URL: str) -> tuple[list[str], str | None]:
    cached_article = cache.get_cached_json(
        "news_articles", news_URL, NEWS_ARTICLE_CACHE_TTL_SECONDS
    )
    if cached_article is not None:
        return (
            cached_article.get("paragraphs", []),
            cached_article.get("article_status"),
        )

    response = requests.get(news_URL, headers=headers)
    response_text = response.text
    response_text_lower = response_text.lower()

    if urlparse(news_URL).netloc == "finance.yahoo.com" and any(
        marker in response_text_lower for marker in YAHOO_PREMIUM_MARKERS
    ):
        print(f"Skipping premium Yahoo Finance article: {news_URL}")
        cache.set_cached_json(
            "news_articles",
            news_URL,
            {"paragraphs": [], "article_status": "premium"},
        )
        return [], "premium"

    soup = BeautifulSoup(response_text, "html.parser")

    news_body = soup.select_one(".body")

    news_paragraphs = []
    if news_body:
        for child in news_body.select("p"):
            text = child.get_text().strip()
            if text:
                news_paragraphs.append(text)

    else:
        print("No element found with class name: body")
        return [], "unavailable"

    if not news_paragraphs:
        print(f"No readable paragraphs found: {news_URL}")
        return [], "unavailable"

    cache.set_cached_json(
        "news_articles",
        news_URL,
        {"paragraphs": news_paragraphs, "article_status": None},
    )
    return news_paragraphs, None
