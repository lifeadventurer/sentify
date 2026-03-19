import csv
import json

from config.constants import (
    COMPANIES_CSV_FILE,
    COMPANIES_TO_TICKER_SYMBOL_JSON_FILE,
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


def check_company_exists(input_company: str) -> tuple[bool, tuple[str, str]]:
    with open(COMPANIES_TO_TICKER_SYMBOL_JSON_FILE) as file:
        companies_to_ticker_symbol = json.load(file)

    for name, ticker in companies_to_ticker_symbol.items():
        if input_company.lower() in [name.lower(), ticker.lower()]:
            return True, (name, ticker)

    return False, ("", "")


if __name__ == "__main__":
    generate_companies_to_ticker_symbol_json_file()
