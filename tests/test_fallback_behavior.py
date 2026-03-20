import json
import sys
import tempfile
import time
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


def _install_flask_stub() -> None:
    if "flask" in sys.modules:
        return

    module = types.ModuleType("flask")

    class Flask:
        def __init__(self, *_args, **_kwargs) -> None:
            self.routes = {}

        def route(self, rule, **kwargs):
            def decorator(func):
                methods = tuple(kwargs.get("methods", ["GET"]))
                self.routes[(rule, methods)] = func
                return func

            return decorator

    module.Flask = Flask
    module.render_template = lambda *_args, **_kwargs: None
    module.request = types.SimpleNamespace(form={})
    sys.modules["flask"] = module


def _install_torch_stub() -> None:
    if "torch" in sys.modules:
        return

    module = types.ModuleType("torch")
    module.Tensor = object
    module.nn = types.SimpleNamespace(
        functional=types.SimpleNamespace(softmax=lambda *_args, **_kwargs: None)
    )
    sys.modules["torch"] = module


def _install_transformers_stub() -> None:
    if "transformers" in sys.modules:
        return

    module = types.ModuleType("transformers")

    class AutoTokenizer:
        @staticmethod
        def from_pretrained(*_args, **_kwargs):
            return object()

    class AutoModelForSequenceClassification:
        @staticmethod
        def from_pretrained(*_args, **_kwargs):
            return object()

    module.AutoTokenizer = AutoTokenizer
    module.AutoModelForSequenceClassification = (
        AutoModelForSequenceClassification
    )
    sys.modules["transformers"] = module


_install_requests_stub()
_install_bs4_stub()
_install_flask_stub()
_install_torch_stub()
_install_transformers_stub()

from app import flask_app  # noqa: E402
from scrapers import yahoo_news_scraper  # noqa: E402
from utils import cache, sentiment_analyzer  # noqa: E402


class FallbackBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name)
        self.cache_patcher = patch.object(
            cache, "SENTIFY_CACHE_DIR", self.cache_dir
        )
        self.cache_patcher.start()

    def tearDown(self) -> None:
        self.cache_patcher.stop()
        self.temp_dir.cleanup()

    def _age_cache(
        self,
        namespace: str,
        key: str,
        seconds_old: int,
    ) -> None:
        cache_file = cache._cache_file_path(namespace, key)
        payload = json.loads(cache_file.read_text())
        payload["cached_at"] = time.time() - seconds_old
        cache_file.write_text(json.dumps(payload))

    def test_offline_mode_reuses_stale_exact_news_cache(self) -> None:
        start_timestamp = "2026-03-10T00:00:00Z"
        end_timestamp = "2026-03-12T00:00:00Z"
        cache_key = yahoo_news_scraper._get_news_list_cache_key(
            "AAPL",
            start_timestamp,
            end_timestamp,
            True,
        )
        cached_news = [
            {
                "publish_date": "2026-03-11T00:00:00Z",
                "news_URL": "https://example.com/story",
                "news_title": "Apple story",
            }
        ]
        cache.set_cached_json("news_urls", cache_key, cached_news)
        self._age_cache(
            "news_urls",
            cache_key,
            yahoo_news_scraper.NEWS_LIST_CACHE_TTL_SECONDS + 1,
        )

        with patch.object(yahoo_news_scraper, "OFFLINE_MODE", True):
            news, source = yahoo_news_scraper.get_news_URLs(
                "AAPL",
                start_timestamp,
                end_timestamp,
                title_flag=True,
            )

        self.assertEqual(cached_news, news)
        self.assertEqual("stale_cache", source)

    def test_network_failure_reuses_stale_exact_news_cache(self) -> None:
        start_timestamp = "2026-03-10T00:00:00Z"
        end_timestamp = "2026-03-12T00:00:00Z"
        cache_key = yahoo_news_scraper._get_news_list_cache_key(
            "AAPL",
            start_timestamp,
            end_timestamp,
            True,
        )
        cached_news = [
            {
                "publish_date": "2026-03-10T12:00:00Z",
                "news_URL": "https://example.com/network-fallback",
                "news_title": "Apple fallback",
            }
        ]
        cache.set_cached_json("news_urls", cache_key, cached_news)
        self._age_cache(
            "news_urls",
            cache_key,
            yahoo_news_scraper.NEWS_LIST_CACHE_TTL_SECONDS + 1,
        )

        with (
            patch.object(yahoo_news_scraper, "OFFLINE_MODE", False),
            patch.object(
                yahoo_news_scraper.requests,
                "post",
                side_effect=yahoo_news_scraper.requests.RequestException(
                    "boom"
                ),
            ),
        ):
            news, source = yahoo_news_scraper.get_news_URLs(
                "AAPL",
                start_timestamp,
                end_timestamp,
                title_flag=True,
            )

        self.assertEqual(cached_news, news)
        self.assertEqual("stale_cache", source)

    def test_legacy_dict_shaped_news_cache_is_normalized(self) -> None:
        start_timestamp = "2026-03-10T00:00:00Z"
        end_timestamp = "2026-03-12T00:00:00Z"
        cache_key = yahoo_news_scraper._get_news_list_cache_key(
            "AAPL",
            start_timestamp,
            end_timestamp,
            True,
        )
        cached_news = [
            {
                "publish_date": "2026-03-11T00:00:00Z",
                "news_URL": "https://example.com/legacy-cache",
                "news_title": "Apple legacy cache",
            }
        ]
        cache.set_cached_json(
            "news_urls",
            cache_key,
            {"metadata": {"old": True}, "items": cached_news},
        )

        news, source = yahoo_news_scraper.get_news_URLs(
            "AAPL",
            start_timestamp,
            end_timestamp,
            title_flag=True,
        )

        self.assertEqual(cached_news, news)
        self.assertEqual("cache", source)

    def test_fresh_exact_news_cache_keeps_cache_source(self) -> None:
        start_timestamp = "2026-03-10T00:00:00Z"
        end_timestamp = "2026-03-12T00:00:00Z"
        cache_key = yahoo_news_scraper._get_news_list_cache_key(
            "AAPL",
            start_timestamp,
            end_timestamp,
            True,
        )
        cached_news = [
            {
                "publish_date": "2026-03-11T00:00:00Z",
                "news_URL": "https://example.com/fresh-cache",
                "news_title": "Apple fresh cache",
            }
        ]
        cache.set_cached_json("news_urls", cache_key, cached_news)

        news, source = yahoo_news_scraper.get_news_URLs(
            "AAPL",
            start_timestamp,
            end_timestamp,
            title_flag=True,
        )

        self.assertEqual(cached_news, news)
        self.assertEqual("cache", source)

    def test_offline_mode_without_exact_news_cache_returns_unavailable(
        self,
    ) -> None:
        with patch.object(yahoo_news_scraper, "OFFLINE_MODE", True):
            news, source = yahoo_news_scraper.get_news_URLs(
                "AAPL",
                "2026-03-10T00:00:00Z",
                "2026-03-12T00:00:00Z",
                title_flag=True,
            )

        self.assertEqual([], news)
        self.assertEqual("offline_unavailable", source)

    def test_network_failure_reuses_stale_exact_article_cache(self) -> None:
        news_url = "https://example.com/article"
        cached_article = {
            "paragraphs": ["cached paragraph"],
            "article_status": None,
        }
        cache.set_cached_json("news_articles", news_url, cached_article)
        self._age_cache(
            "news_articles",
            news_url,
            yahoo_news_scraper.NEWS_ARTICLE_CACHE_TTL_SECONDS + 1,
        )

        with (
            patch.object(yahoo_news_scraper, "OFFLINE_MODE", False),
            patch.object(
                yahoo_news_scraper.requests,
                "get",
                side_effect=yahoo_news_scraper.requests.RequestException(
                    "boom"
                ),
            ),
        ):
            paragraphs, article_status = yahoo_news_scraper.get_news_paragraphs(
                news_url
            )

        self.assertEqual(["cached paragraph"], paragraphs)
        self.assertIsNone(article_status)

    def test_calculate_paragraph_score_reuses_stale_sentiment_cache(
        self,
    ) -> None:
        news_item = {
            "news_URL": "https://example.com/sentiment",
            "publish_date": "2026-03-12T00:00:00Z",
        }
        current_timestamp = "2026-03-13T00:00:00Z"
        cache_key = flask_app._get_sentiment_cache_key(news_item["news_URL"])
        cached_sentiment = {
            "paragraphs": [{"content": "cached", "positive_score": " 0.900"}],
            "overall_sentiment_score": {
                "label": "positive",
                "score": " 0.900",
            },
            "sentiment_scores_of_new": {
                "label": "positive",
                "highest_score": 0.9,
                "corresponding_score": 0.1,
            },
        }
        cache.set_cached_json("news_sentiment", cache_key, cached_sentiment)
        self._age_cache(
            "news_sentiment",
            cache_key,
            flask_app.SENTIMENT_CACHE_TTL_SECONDS + 1,
        )

        with patch.object(
            yahoo_news_scraper,
            "get_news_paragraphs",
            return_value=([], "unavailable"),
        ):
            news, sentiment_scores = flask_app.calculate_paragraph_score(
                news_item,
                current_timestamp,
                model_available=False,
            )

        self.assertEqual(
            cached_sentiment["overall_sentiment_score"],
            news["overall_sentiment_score"],
        )
        self.assertEqual(cached_sentiment["paragraphs"], news["paragraphs"])
        self.assertEqual("positive", sentiment_scores["label"])
        self.assertEqual(0.9, sentiment_scores["highest_score"])
        self.assertEqual(0.1, sentiment_scores["corresponding_score"])
        self.assertEqual(86400, sentiment_scores["age_seconds"])
        self.assertEqual(1, sentiment_scores["content_length_words"])

    def test_empty_cached_sentiment_summary_stays_empty(self) -> None:
        news_item = {
            "news_URL": "https://example.com/legacy-sentiment",
            "publish_date": "2026-03-12T00:00:00Z",
        }
        current_timestamp = "2026-03-13T00:00:00Z"
        cache_key = flask_app._get_sentiment_cache_key(news_item["news_URL"])
        cache.set_cached_json(
            "news_sentiment",
            cache_key,
            {
                "paragraphs": [],
                "overall_sentiment_score": {},
                "sentiment_scores_of_new": {},
            },
        )
        self._age_cache(
            "news_sentiment",
            cache_key,
            flask_app.SENTIMENT_CACHE_TTL_SECONDS + 1,
        )

        with patch.object(
            yahoo_news_scraper,
            "get_news_paragraphs",
            return_value=([], "unavailable"),
        ):
            _news, sentiment_scores = flask_app.calculate_paragraph_score(
                news_item,
                current_timestamp,
                model_available=False,
            )

        self.assertEqual({}, sentiment_scores)

    def test_age_seconds_uses_actual_now_not_window_end(self) -> None:
        news_item = {
            "news_URL": "https://example.com/older-window-sentiment",
            "publish_date": "2026-03-12T00:00:00Z",
        }
        current_timestamp = "2026-03-13T00:00:00Z"
        actual_timestamp = "2026-03-23T00:00:00Z"
        cache_key = flask_app._get_sentiment_cache_key(news_item["news_URL"])
        cache.set_cached_json(
            "news_sentiment",
            cache_key,
            {
                "paragraphs": [
                    {"content": "cached", "positive_score": " 0.900"}
                ],
                "overall_sentiment_score": {
                    "label": "positive",
                    "score": " 0.900",
                },
                "sentiment_scores_of_new": {
                    "label": "positive",
                    "highest_score": 0.9,
                    "corresponding_score": 0.1,
                },
            },
        )
        self._age_cache(
            "news_sentiment",
            cache_key,
            flask_app.SENTIMENT_CACHE_TTL_SECONDS + 1,
        )

        with patch.object(
            yahoo_news_scraper,
            "get_news_paragraphs",
            return_value=([], "unavailable"),
        ):
            _news, sentiment_scores = flask_app.calculate_paragraph_score(
                news_item,
                current_timestamp,
                actual_timestamp,
                model_available=False,
            )

        self.assertEqual(11 * 86400, sentiment_scores["age_seconds"])

    def test_model_cache_identity_ignores_offline_mode(self) -> None:
        with patch.object(
            sentiment_analyzer, "SENTIMENT_MODEL_LOCAL_FILES_ONLY", False
        ):
            with patch.object(sentiment_analyzer, "OFFLINE_MODE", False):
                online_identity = sentiment_analyzer.get_model_cache_identity()
            with patch.object(sentiment_analyzer, "OFFLINE_MODE", True):
                offline_identity = sentiment_analyzer.get_model_cache_identity()

        self.assertEqual(online_identity, offline_identity)

    def test_search_shows_stale_cache_message_when_live_fetch_fails(
        self,
    ) -> None:
        app = flask_app.create_app()
        search = app.routes[("/", ("POST",))]

        with (
            patch.object(flask_app.request, "form", {"company": "AAPL"}),
            patch.object(
                flask_app.data,
                "check_company_exists",
                return_value=(True, ("Apple Inc.", "AAPL")),
            ),
            patch.object(
                flask_app.yahoo_news_scraper,
                "get_news_URLs",
                return_value=([], "stale_cache"),
            ),
            patch.object(
                flask_app,
                "render_template",
                side_effect=lambda *_args, **kwargs: kwargs,
            ),
            patch.object(flask_app, "OFFLINE_MODE", False),
        ):
            response = search()

        self.assertEqual(
            "Live news fetch failed. Showing stale cached news and sentiment where available.",
            response["message"],
        )

    def test_search_preserves_stale_cache_warning_when_model_load_fails(
        self,
    ) -> None:
        app = flask_app.create_app()
        search = app.routes[("/", ("POST",))]

        with (
            patch.object(flask_app.request, "form", {"company": "AAPL"}),
            patch.object(
                flask_app.data,
                "check_company_exists",
                return_value=(True, ("Apple Inc.", "AAPL")),
            ),
            patch.object(
                flask_app.yahoo_news_scraper,
                "get_news_URLs",
                return_value=(
                    [
                        {
                            "news_URL": "https://example.com/article",
                            "publish_date": "2026-03-10T00:00:00Z",
                            "news_title": "Apple stale cache",
                        }
                    ],
                    "stale_cache",
                ),
            ),
            patch.object(
                flask_app.sentiment_analyzer,
                "preload_model",
                side_effect=RuntimeError("no local model"),
            ),
            patch.object(flask_app, "OFFLINE_MODE", True),
            patch.object(flask_app, "Pool") as pool_cls,
            patch.object(
                flask_app,
                "render_template",
                side_effect=lambda *_args, **kwargs: kwargs,
            ),
        ):

            class DummyPool:
                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return False

                def starmap(self, _func, _args):
                    return [
                        (
                            {
                                "article_status": "model_unavailable",
                                "paragraphs": [],
                            },
                            {},
                        )
                    ]

            pool_cls.return_value = DummyPool()
            response = search()

        self.assertEqual(
            "Offline mode is enabled. Showing stale cached news and sentiment where available. "
            "Offline mode is enabled. Cached news is shown where available, but uncached articles "
            "could not be analyzed because no local sentiment model was found.",
            response["message"],
        )

    def test_search_passes_ui_weight_overrides_to_recommendation(self) -> None:
        app = flask_app.create_app()
        search = app.routes[("/", ("POST",))]

        with (
            patch.object(
                flask_app.request,
                "form",
                {
                    "company": "AAPL",
                    "recency_half_life_hours": "48",
                    "recency_floor": "0.35",
                    "content_length_target_words": "600",
                    "content_length_min": "0.9",
                    "content_length_max": "1.8",
                },
            ),
            patch.object(
                flask_app.data,
                "check_company_exists",
                return_value=(True, ("Apple Inc.", "AAPL")),
            ),
            patch.object(
                flask_app.yahoo_news_scraper,
                "get_news_URLs",
                return_value=(
                    [
                        {
                            "news_URL": "https://example.com/article",
                            "publish_date": "2026-03-10T00:00:00Z",
                            "news_title": "Apple weighting",
                        }
                    ],
                    "live",
                ),
            ),
            patch.object(flask_app.sentiment_analyzer, "preload_model"),
            patch.object(flask_app, "Pool") as pool_cls,
            patch.object(
                flask_app.action,
                "get_recommended_action",
                return_value=("Buy", 0.9),
            ) as get_recommended_action,
            patch.object(
                flask_app,
                "render_template",
                side_effect=lambda *_args, **kwargs: kwargs,
            ),
        ):

            class DummyPool:
                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    return False

                def starmap(self, _func, _args):
                    return [
                        (
                            {
                                "paragraphs": [],
                                "overall_sentiment_score": {},
                            },
                            {
                                "label": "Positive",
                                "highest_score": 0.8,
                                "corresponding_score": 0.1,
                                "content_length_words": 500,
                            },
                        )
                    ]

            pool_cls.return_value = DummyPool()
            response = search()

        get_recommended_action.assert_called_once_with(
            [
                {
                    "label": "Positive",
                    "highest_score": 0.8,
                    "corresponding_score": 0.1,
                    "content_length_words": 500,
                }
            ],
            {
                "recency_half_life_hours": 48.0,
                "recency_floor": 0.35,
                "content_length_target_words": 600,
                "content_length_min": 0.9,
                "content_length_max": 1.8,
            },
        )
        self.assertEqual(
            48.0, response["weight_config"]["recency_half_life_hours"]
        )
        self.assertEqual(1.8, response["weight_config"]["content_length_max"])

    def test_create_app_uses_cache_retention_ttls_for_cleanup(self) -> None:
        with (
            patch.object(flask_app, "NEWS_LIST_CACHE_RETENTION_SECONDS", 3600),
            patch.object(
                flask_app, "NEWS_ARTICLE_CACHE_RETENTION_SECONDS", 7200
            ),
            patch.object(flask_app, "SENTIMENT_CACHE_RETENTION_SECONDS", 14400),
            patch.object(flask_app.cache, "cleanup_expired_json") as cleanup,
        ):
            flask_app.create_app()

        cleanup.assert_called_once_with(
            {
                "news_urls": 3600,
                "news_articles": 7200,
                "news_sentiment": 14400,
            }
        )


if __name__ == "__main__":
    unittest.main()
