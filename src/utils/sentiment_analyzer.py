from functools import lru_cache
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from config.config import (
    SENTIMENT_MODEL_ID,
    SENTIMENT_MODEL_LOCAL_FILES_ONLY,
    SENTIMENT_MODEL_PATH,
    SENTIMENT_MODEL_REVISION,
)
from config.constants import NEGATIVE, NEUTRAL, POSITIVE


def _get_model_source() -> str:
    if SENTIMENT_MODEL_PATH:
        return str(Path(SENTIMENT_MODEL_PATH).expanduser())

    return SENTIMENT_MODEL_ID


def _get_model_load_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "local_files_only": SENTIMENT_MODEL_LOCAL_FILES_ONLY,
    }

    if SENTIMENT_MODEL_REVISION and not SENTIMENT_MODEL_PATH:
        kwargs["revision"] = SENTIMENT_MODEL_REVISION

    return kwargs


@lru_cache(maxsize=1)
def get_tokenizer() -> AutoTokenizer:
    return AutoTokenizer.from_pretrained(
        _get_model_source(), **_get_model_load_kwargs()
    )


@lru_cache(maxsize=1)
def get_model() -> AutoModelForSequenceClassification:
    return AutoModelForSequenceClassification.from_pretrained(
        _get_model_source(), **_get_model_load_kwargs()
    )


def preload_model() -> None:
    get_tokenizer()
    get_model()


def predict(text: str) -> torch.Tensor:
    tokenizer = get_tokenizer()
    model = get_model()
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
    outputs = model(**inputs)
    predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
    return predictions


def get_sentiment_score(input_str: str) -> tuple[float, float, float]:
    """
    Predicts the sentiment scores for the given input string.

    Args:
        input_str (str): The input string for which the sentiment score is to be predicted.

    Returns:
        tuple[float, float, float]: A tuple containing three float values representing the sentiment scores:
            - negative_prob: The probability that the sentiment is negative.
            - neutral_prob: The probability that the sentiment is neutral.
            - positive_prob: The probability that the sentiment is positive.
    """
    return predict(input_str).tolist()[0]


def get_overall_sentiment_score(
    paragraphs_with_sentiment_scores: list[dict],
) -> tuple[str, float, float]:
    paragraph_count = len(paragraphs_with_sentiment_scores)

    if paragraph_count == 0:
        return NEUTRAL, 0.0, 0.0

    positive_score_sum, neutral_score_sum, negative_score_sum = 0.0, 0.0, 0.0
    for item in paragraphs_with_sentiment_scores:
        positive_score = float(item["positive_score"])
        neutral_score = float(item["neutral_score"])
        negative_score = float(item["negative_score"])

        positive_score_sum += positive_score
        neutral_score_sum += neutral_score
        negative_score_sum += negative_score

    if neutral_score_sum / paragraph_count >= 0.8:
        return NEUTRAL, neutral_score_sum / paragraph_count, 0.0

    positive_score_sum, negative_score_sum, paragraph_count = 0.0, 0.0, 0
    for item in paragraphs_with_sentiment_scores:
        positive_score = float(item["positive_score"])
        neutral_score = float(item["neutral_score"])
        negative_score = float(item["negative_score"])
        if neutral_score == max(positive_score, neutral_score, negative_score):
            continue
        positive_score_sum += positive_score
        negative_score_sum += negative_score
        paragraph_count += 1

    if paragraph_count == 0:
        return (
            NEUTRAL,
            neutral_score_sum / len(paragraphs_with_sentiment_scores),
            0.0,
        )

    if positive_score_sum > negative_score_sum:
        return (
            POSITIVE,
            positive_score_sum / paragraph_count,
            negative_score_sum / paragraph_count,
        )

    return (
        NEGATIVE,
        negative_score_sum / paragraph_count,
        positive_score_sum / paragraph_count,
    )


# Example usage
if __name__ == "__main__":
    input_str = "Input your message here."
    negative_prob, neutral_prob, positive_prob = get_sentiment_score(input_str)
