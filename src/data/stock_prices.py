import logging

import pandas
import yfinance as yf

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def get_stock_prices(
    ticker_symbol: str, start_datetime: str, end_datetime: str
) -> pandas.DataFrame | None:
    try:
        data = yf.download(
            ticker_symbol, start=start_datetime, end=end_datetime, interval="1d"
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.warning(
            "Failed to download stock prices for %s between %s and %s: %s",
            ticker_symbol,
            start_datetime,
            end_datetime,
            exc,
        )
        return None

    if data is None:
        logger.warning(
            "No stock price data object was returned for %s between %s and %s.",
            ticker_symbol,
            start_datetime,
            end_datetime,
        )
        return None

    try:
        # Drop the last two columns - Adj Close, Volume
        return data.drop(data.columns[-2:], axis=1)
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "Failed to normalize stock prices for %s between %s and %s: %s",
            ticker_symbol,
            start_datetime,
            end_datetime,
            exc,
        )
        return None


# Example usage
if __name__ == "__main__":
    ticker_symbol = "AAPL"
    start_datetime = "2024-07-08"
    end_datetime = "2024-07-15"

    data = get_stock_prices(ticker_symbol, start_datetime, end_datetime)
    if data is not None:
        print(data.to_csv())
