import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from utils import action  # noqa: E402


class ActionWeightingTests(unittest.TestCase):
    def test_recency_weight_defaults_to_one_without_age(self) -> None:
        self.assertEqual(1.0, action.get_recency_weight(None))

    def test_content_length_weight_defaults_to_one_without_length(self) -> None:
        self.assertEqual(1.0, action.get_content_length_weight(None))

    def test_recency_weight_decays_but_respects_floor(self) -> None:
        with (
            patch.object(action, "RECENCY_WEIGHT_HALF_LIFE_HOURS", 24.0),
            patch.object(action, "RECENCY_WEIGHT_FLOOR", 0.2),
        ):
            newest_weight = action.get_recency_weight(0)
            one_day_weight = action.get_recency_weight(86400)
            very_old_weight = action.get_recency_weight(86400 * 365)

        self.assertEqual(1.0, newest_weight)
        self.assertAlmostEqual(0.6, one_day_weight, places=3)
        self.assertGreaterEqual(very_old_weight, 0.2)
        self.assertLess(very_old_weight, 0.21)

    def test_content_length_weight_scales_between_min_and_max(self) -> None:
        with (
            patch.object(action, "CONTENT_LENGTH_WEIGHT_TARGET_WORDS", 400),
            patch.object(action, "CONTENT_LENGTH_WEIGHT_MIN", 0.75),
            patch.object(action, "CONTENT_LENGTH_WEIGHT_MAX", 1.25),
        ):
            self.assertEqual(0.75, action.get_content_length_weight(0))
            self.assertAlmostEqual(
                0.875,
                action.get_content_length_weight(100),
                places=3,
            )
            self.assertEqual(1.25, action.get_content_length_weight(800))

    def test_recent_news_outweighs_older_opposing_news(self) -> None:
        with (
            patch.object(action, "RECENCY_WEIGHT_HALF_LIFE_HOURS", 24.0),
            patch.object(action, "RECENCY_WEIGHT_FLOOR", 0.2),
        ):
            recommended_action, confidence_index = (
                action.get_recommended_action(
                    [
                        {
                            "label": "Positive",
                            "highest_score": 0.75,
                            "corresponding_score": 0.2,
                            "age_seconds": 86400 * 30,
                        },
                        {
                            "label": "Negative",
                            "highest_score": 0.9,
                            "corresponding_score": 0.1,
                            "age_seconds": 3600,
                        },
                    ]
                )
            )

        self.assertEqual("Sell", recommended_action)
        self.assertGreater(confidence_index, 0.5)

    def test_longer_article_outweighs_shorter_opposing_article(self) -> None:
        with (
            patch.object(action, "RECENCY_WEIGHT_HALF_LIFE_HOURS", 0.0),
            patch.object(action, "CONTENT_LENGTH_WEIGHT_TARGET_WORDS", 400),
            patch.object(action, "CONTENT_LENGTH_WEIGHT_MIN", 0.75),
            patch.object(action, "CONTENT_LENGTH_WEIGHT_MAX", 1.25),
        ):
            recommended_action, confidence_index = (
                action.get_recommended_action(
                    [
                        {
                            "label": "Positive",
                            "highest_score": 0.99,
                            "corresponding_score": 0.01,
                            "content_length_words": 600,
                        },
                        {
                            "label": "Negative",
                            "highest_score": 0.7,
                            "corresponding_score": 0.3,
                            "content_length_words": 20,
                        },
                    ]
                )
            )

        self.assertEqual("Buy", recommended_action)
        self.assertGreater(confidence_index, 0.5)

    def test_weight_config_overrides_module_defaults(self) -> None:
        with (
            patch.object(action, "RECENCY_WEIGHT_HALF_LIFE_HOURS", 24.0),
            patch.object(action, "RECENCY_WEIGHT_FLOOR", 0.2),
            patch.object(action, "CONTENT_LENGTH_WEIGHT_TARGET_WORDS", 400),
            patch.object(action, "CONTENT_LENGTH_WEIGHT_MIN", 0.75),
            patch.object(action, "CONTENT_LENGTH_WEIGHT_MAX", 1.25),
        ):
            default_weight = action.get_article_weight(
                {
                    "age_seconds": 86400,
                    "content_length_words": 100,
                }
            )
            override_weight = action.get_article_weight(
                {
                    "age_seconds": 86400,
                    "content_length_words": 100,
                },
                {
                    "recency_half_life_hours": 48,
                    "recency_floor": 0.4,
                    "content_length_target_words": 200,
                    "content_length_min": 1.0,
                    "content_length_max": 2.0,
                },
            )

        self.assertAlmostEqual(0.525, default_weight, places=3)
        self.assertAlmostEqual(1.236, override_weight, places=3)


if __name__ == "__main__":
    unittest.main()
