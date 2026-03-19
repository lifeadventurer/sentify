![](./sentify_logo.png)

This project focuses on analyzing the sentiment of news articles to predict stock trends. It features a Flask-based web application designed to provide real-time financial data analysis and sentiment tracking.

- **Input**: Users can enter a company name or ticker symbol to retrieve relevant news articles.
- **Process**: Each news article is analyzed for sentiment, with scores generated to gauge the article's impact on stock trends.
- **Output**: The application delivers actionable insights and confidence indices based on the sentiment analysis, helping investors make informed decisions about their investments.

## Prerequisites

Before you begin, make sure you have the following installed:

- Python (version 3.11 or higher)
- uv (recommended)
- or pip

## Installation

### Using uv (recommended)

1. Clone the repository:

   ```shell
   git clone https://github.com/LifeAdventurer/sentify.git
   cd sentify
   ```

2. Install dependencies:

   ```shell
   uv sync
   ```

3. Activate the virtual environment:

   ```shell
   source .venv/bin/activate # On Windows use `.venv\Scripts\activate`
   ```

### Using pip

1. Clone the repository:

   ```shell
   git clone https://github.com/LifeAdventurer/sentify.git
   cd sentify
   ```

2. Create and activate a virtual environment:

   ```shell
   python -m venv venv
   source venv/bin/activate # On Windows use `venv\Scripts\activate`
   ```

3. Install dependencies:

   ```shell
   pip install -r requirements.txt
   ```

## Usage

To serve the Flask app locally, run:

```
uv run python src/main.py
```

Optional model overrides:

```shell
export SENTIFY_MODEL_PATH="/path/to/local/model"
export SENTIFY_MODEL_ID="marcev/financebert"
export SENTIFY_MODEL_REVISION="<pinned-revision>"
export SENTIFY_MODEL_LOCAL_FILES_ONLY=true
export SENTIFY_CACHE_DIR="/path/to/cache"
export SENTIFY_NEWS_LIST_CACHE_TTL_SECONDS=900
export SENTIFY_NEWS_ARTICLE_CACHE_TTL_SECONDS=5184000
export SENTIFY_SENTIMENT_CACHE_TTL_SECONDS=5184000
```

## Configuration

To configure the application, update the `config.py` file in the `src/config` directory. Key parameters include:

```
TOP_COMPANIES_COUNT = 10000
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
UTC_DIFFERENCE = 8
MAX_NEWS_LOOKBACK_DAYS = 60
CPU_COUNT = 2
```

- `TOP_COMPANIES_COUNT`: The number of top companies ranked by market cap to search.
- `TIMESTAMP_FORMAT`: The format for timestamps used in the application, especially for the news API.
- `UTC_DIFFERENCE`: The difference in hours between local time and UTC.
- `MAX_NEWS_LOOKBACK_DAYS`: The max number of days to look back when fetching news articles.
- `CPU_COUNT`: The number of CPUs to be used for multiprocessing.
- `SENTIFY_MODEL_PATH`: Local model directory override. If set, it takes precedence over the remote model id.
- `SENTIFY_MODEL_ID`: Hugging Face model id to use when no local path override is set.
- `SENTIFY_MODEL_REVISION`: Optional pinned revision for reproducible Hugging Face loads.
- `SENTIFY_MODEL_LOCAL_FILES_ONLY`: Forces local-only loading when set to `true`, `1`, `yes`, or `on`.
- `SENTIFY_CACHE_DIR`: Directory for cached Yahoo news responses. Defaults to `.cache/sentify` in the repository root.
- `SENTIFY_NEWS_LIST_CACHE_TTL_SECONDS`: How long ticker news query results stay fresh. Defaults to 900 seconds.
- `SENTIFY_NEWS_ARTICLE_CACHE_TTL_SECONDS`: How long article body fetches stay fresh. Defaults to `MAX_NEWS_LOOKBACK_DAYS * 86400` seconds.
- `SENTIFY_SENTIMENT_CACHE_TTL_SECONDS`: How long article sentiment results stay fresh. Defaults to `MAX_NEWS_LOOKBACK_DAYS * 86400` seconds.

## LICENSE

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](./LICENSE) file for details.
