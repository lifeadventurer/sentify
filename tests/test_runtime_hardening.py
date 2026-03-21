import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _install_requests_stub() -> None:
    if "requests" in sys.modules:
        return

    module = types.ModuleType("requests")

    class RequestException(Exception):
        pass

    module.RequestException = RequestException
    module.get = None
    module.post = None
    sys.modules["requests"] = module


def _install_bs4_stub() -> None:
    if "bs4" in sys.modules:
        return

    module = types.ModuleType("bs4")

    class BeautifulSoup:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def select_one(self, *_args, **_kwargs):
            return None

    module.BeautifulSoup = BeautifulSoup
    sys.modules["bs4"] = module


def _install_pandas_stub() -> None:
    if "pandas" in sys.modules:
        return

    module = types.ModuleType("pandas")
    module.DataFrame = object
    sys.modules["pandas"] = module


def _install_yfinance_stub() -> None:
    if "yfinance" in sys.modules:
        return

    module = types.ModuleType("yfinance")
    module.download = None
    sys.modules["yfinance"] = module


_install_requests_stub()
_install_bs4_stub()
_install_pandas_stub()
_install_yfinance_stub()

from data import stock_prices  # noqa: E402
from scrapers import yahoo_news_scraper  # noqa: E402


class RuntimeHardeningTests(unittest.TestCase):
    def test_news_list_request_uses_timeout(self) -> None:
        class Response:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "data": {
                        "tickerStream": {
                            "stream": [],
                            "pagination": {"uuids": ""},
                        }
                    }
                }

        with (
            patch.object(
                yahoo_news_scraper.cache,
                "get_cached_json",
                return_value=None,
            ),
            patch.object(
                yahoo_news_scraper.cache,
                "set_cached_json",
            ),
            patch.object(
                yahoo_news_scraper.requests,
                "post",
                return_value=Response(),
            ) as post,
        ):
            news, source = yahoo_news_scraper.get_news_URLs(
                "AAPL",
                "2026-03-10T00:00:00Z",
                "2026-03-12T00:00:00Z",
            )

        self.assertEqual([], news)
        self.assertEqual("live", source)
        self.assertEqual(
            yahoo_news_scraper.REQUEST_TIMEOUT_SECONDS,
            post.call_args.kwargs["timeout"],
        )

    def test_empty_news_page_without_pagination_returns_live_empty_result(
        self,
    ) -> None:
        start_timestamp = "2026-03-10T00:00:00Z"
        end_timestamp = "2026-03-12T00:00:00Z"

        class Response:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "data": {
                        "tickerStream": {
                            "stream": [],
                        }
                    }
                }

        with (
            patch.object(
                yahoo_news_scraper.cache,
                "get_cached_json",
                return_value=None,
            ),
            patch.object(yahoo_news_scraper.cache, "set_cached_json"),
            patch.object(
                yahoo_news_scraper.requests,
                "post",
                return_value=Response(),
            ),
        ):
            news, source = yahoo_news_scraper.get_news_URLs(
                "AAPL",
                start_timestamp,
                end_timestamp,
            )

        self.assertEqual([], news)
        self.assertEqual("live", source)

    def test_malformed_news_pagination_falls_back_to_stale_cache(self) -> None:
        start_timestamp = "2026-03-10T00:00:00Z"
        end_timestamp = "2026-03-12T00:00:00Z"
        cached_news = [
            {
                "publish_date": "2026-03-10T12:00:00Z",
                "news_URL": "https://example.com/network-fallback",
                "news_title": "Apple fallback",
            }
        ]

        class Response:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "data": {
                        "tickerStream": {
                            "stream": [
                                {
                                    "content": {
                                        "clickThroughUrl": {
                                            "url": "https://example.com/story"
                                        },
                                        "pubDate": "2026-03-11T00:00:00Z",
                                        "title": "Apple story",
                                    }
                                }
                            ],
                        }
                    }
                }

        with (
            patch.object(
                yahoo_news_scraper.cache,
                "get_cached_json",
                side_effect=[None, cached_news],
            ),
            patch.object(yahoo_news_scraper.cache, "set_cached_json"),
            patch.object(
                yahoo_news_scraper.requests,
                "post",
                return_value=Response(),
            ),
        ):
            news, source = yahoo_news_scraper.get_news_URLs(
                "AAPL",
                start_timestamp,
                end_timestamp,
            )

        self.assertEqual(cached_news, news)
        self.assertEqual("stale_cache", source)

    def test_article_request_uses_timeout(self) -> None:
        class Response:
            status_code = 200
            text = "<div class='body'><p>hello world</p></div>"

        class Paragraph:
            @staticmethod
            def get_text():
                return "hello world"

        class Body:
            @staticmethod
            def select(_selector):
                return [Paragraph()]

        class Soup:
            def __init__(self, *_args, **_kwargs) -> None:
                pass

            @staticmethod
            def select_one(_selector):
                return Body()

        with (
            patch.object(
                yahoo_news_scraper.cache,
                "get_cached_json",
                return_value=None,
            ),
            patch.object(yahoo_news_scraper.cache, "set_cached_json"),
            patch.object(
                yahoo_news_scraper.requests,
                "get",
                return_value=Response(),
            ) as get,
            patch.object(yahoo_news_scraper, "BeautifulSoup", Soup),
        ):
            paragraphs, article_status = yahoo_news_scraper.get_news_paragraphs(
                "https://example.com/article"
            )

        self.assertEqual(["hello world"], paragraphs)
        self.assertIsNone(article_status)
        self.assertEqual(
            yahoo_news_scraper.REQUEST_TIMEOUT_SECONDS,
            get.call_args.kwargs["timeout"],
        )

    def test_get_stock_prices_preserves_empty_dataframes(self) -> None:
        class FakeFrame:
            def __init__(self, empty: bool) -> None:
                self.empty = empty
                self.columns = [
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Adj Close",
                    "Volume",
                ]

            def drop(self, _columns, axis=0):
                self.drop_axis = axis
                return self

        empty_frame = FakeFrame(empty=True)

        with patch.object(
            stock_prices.yf,
            "download",
            return_value=empty_frame,
        ):
            result = stock_prices.get_stock_prices(
                "AAPL",
                "2026-03-10",
                "2026-03-12",
            )

        self.assertIs(empty_frame, result)

    def test_get_stock_prices_preserves_zero_column_dataframes(self) -> None:
        class FakeFrame:
            def __init__(self) -> None:
                self.empty = True
                self.columns = []

            def drop(self, _columns, axis=0):
                self.drop_axis = axis
                return self

        zero_column_frame = FakeFrame()

        with patch.object(
            stock_prices.yf,
            "download",
            return_value=zero_column_frame,
        ):
            result = stock_prices.get_stock_prices(
                "AAPL",
                "2026-03-10",
                "2026-03-12",
            )

        self.assertIs(zero_column_frame, result)


if __name__ == "__main__":
    unittest.main()
