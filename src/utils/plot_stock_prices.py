import logging

import matplotlib.pyplot as plt
import yfinance as yf

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def plot_minutely_detail(ticker: str, start_datetime: str, end_datetime: str):
    try:
        data = yf.download(
            ticker, start=start_datetime, end=end_datetime, interval="5m"
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.warning(
            "Failed to download minutely stock prices for %s between %s and "
            "%s: %s",
            ticker,
            start_datetime,
            end_datetime,
            exc,
        )
        return

    if data is None or data.empty:
        logger.warning(
            "No minutely stock price data returned for %s between %s and %s.",
            ticker,
            start_datetime,
            end_datetime,
        )
        return

    if "Close" not in data:
        logger.warning(
            "Downloaded minutely stock price data for %s between %s and %s "
            "is missing the Close column.",
            ticker,
            start_datetime,
            end_datetime,
        )
        return

    # data = data.between_time('09:30', '16:00')
    # data = data.reset_index()

    grouped_data = data.groupby(data.index.date)

    try:
        plt.figure(figsize=(10, 6))

        for date, group in grouped_data:
            plt.plot(group.index, group["Close"], label=f"{date}")

        # plt.plot(data.index, data['Close'], label='Close Price', color='blue')
        plt.title(
            f"{ticker} Stock Prices from ({start_datetime} to {end_datetime}) at an interval of 5 minutes"
        )
        plt.xlabel("Datetime")
        plt.ylabel("Price (USD)")
        plt.legend()
        plt.grid(True)
        plt.savefig(
            f"./src/app/static/images/{ticker}_{start_datetime}_to_{end_datetime}.png"
        )
        plt.close()
    except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        plt.close()
        logger.warning(
            "Failed to render minutely stock price plot for %s between %s "
            "and %s: %s",
            ticker,
            start_datetime,
            end_datetime,
            exc,
        )


# Example usage
if __name__ == "__main__":
    ticker_symbol = "AAPL"
    start_datetime = "2024-07-08"
    end_datetime = "2024-07-15"

    plot_minutely_detail(ticker_symbol, start_datetime, end_datetime)
