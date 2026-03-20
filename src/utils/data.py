import csv
import json
import re
import unicodedata

from config.constants import (
    COMPANIES_CSV_FILE,
    COMPANIES_TO_TICKER_SYMBOL_JSON_FILE,
)

SEARCH_TRANSLITERATION_TABLE = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "æ": "ae",
        "Æ": "Ae",
        "œ": "oe",
        "Œ": "Oe",
    }
)


def generate_companies_to_ticker_symbol_json_file(
    top_companies_count: int = 0,
) -> dict:
    companies_to_ticker_symbol = {}

    with open(COMPANIES_CSV_FILE, encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for i, row in enumerate(reader):
            if top_companies_count and i > top_companies_count:
                break
            companies_to_ticker_symbol[row["Name"]] = row["Symbol"]

    with open(
        COMPANIES_TO_TICKER_SYMBOL_JSON_FILE, "w", encoding="utf-8"
    ) as file:
        json.dump(
            companies_to_ticker_symbol,
            file,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        file.write("\n")

    return companies_to_ticker_symbol


def get_company_name_by_ticker(ticker_symbol: str) -> str:
    with open(COMPANIES_TO_TICKER_SYMBOL_JSON_FILE) as file:
        companies_to_ticker_symbol = json.load(file)

    for name, ticker in companies_to_ticker_symbol.items():
        if ticker == ticker_symbol:
            return name

    return ""


def _normalize_search_value(value: str) -> str:
    transliterated = str(value).translate(SEARCH_TRANSLITERATION_TABLE)
    folded = (
        unicodedata.normalize("NFKD", transliterated)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return re.sub(r"\s+", " ", folded.strip().lower())


def _get_search_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize_search_value(value))


def _tokenize_search_value(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", value) if token]


def _get_company_suggestion_label(name: str, ticker: str) -> str:
    return f"{name} ({ticker})"


def check_company_exists(input_company: str) -> tuple[bool, tuple[str, str]]:
    with open(COMPANIES_TO_TICKER_SYMBOL_JSON_FILE) as file:
        companies_to_ticker_symbol = json.load(file)

    normalized_input = _normalize_search_value(input_company)
    input_key = _get_search_key(input_company)
    for name, ticker in companies_to_ticker_symbol.items():
        if normalized_input in {
            _normalize_search_value(name),
            _normalize_search_value(ticker),
            _normalize_search_value(
                _get_company_suggestion_label(name, ticker)
            ),
        } or input_key in {
            _get_search_key(name),
            _get_search_key(ticker),
            _get_search_key(_get_company_suggestion_label(name, ticker)),
        }:
            return True, (name, ticker)

    return False, ("", "")


def get_company_suggestions(
    query: str,
    limit: int = 8,
) -> list[dict[str, str]]:
    normalized_query = _normalize_search_value(query)
    query_key = _get_search_key(query)
    if not normalized_query or not query_key or limit <= 0:
        return []

    with open(COMPANIES_TO_TICKER_SYMBOL_JSON_FILE) as file:
        companies_to_ticker_symbol = json.load(file)

    suggestions: list[tuple[int, int, str, str]] = []
    query_tokens = _tokenize_search_value(normalized_query)

    for index, (name, ticker) in enumerate(companies_to_ticker_symbol.items()):
        normalized_name = _normalize_search_value(name)
        normalized_ticker = _normalize_search_value(ticker)
        normalized_label = _normalize_search_value(
            _get_company_suggestion_label(name, ticker)
        )
        name_key = _get_search_key(name)
        ticker_key = _get_search_key(ticker)
        label_key = _get_search_key(_get_company_suggestion_label(name, ticker))
        name_tokens = _tokenize_search_value(normalized_name)
        score = None

        if normalized_query in {
            normalized_name,
            normalized_ticker,
            normalized_label,
        } or query_key in {name_key, ticker_key, label_key}:
            score = 0
        elif ticker_key.startswith(query_key):
            score = 1
        elif any(
            token.startswith(normalized_query)
            or _get_search_key(token).startswith(query_key)
            for token in name_tokens
        ):
            score = 2
        elif query_key in name_key:
            score = 3
        elif all(token in normalized_name for token in query_tokens):
            score = 4
        elif query_key in ticker_key:
            score = 5

        if score is None:
            continue

        suggestions.append((score, index, name, ticker))

    suggestions.sort(key=lambda item: (item[0], item[1]))
    return [
        {
            "company_name": name,
            "ticker_symbol": ticker,
            "label": _get_company_suggestion_label(name, ticker),
        }
        for _, _, name, ticker in suggestions[:limit]
    ]


if __name__ == "__main__":
    generate_companies_to_ticker_symbol_json_file()
