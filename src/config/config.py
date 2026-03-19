import os


def _get_bool_env(var_name: str, default: bool = False) -> bool:
    value = os.getenv(var_name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


TOP_COMPANIES_COUNT = 10000
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
UTC_DIFFERENCE = 8
CPU_COUNT = 2
MAX_NEWS_LOOKBACK_DAYS = 60

DEFAULT_SENTIMENT_MODEL_ID = "marcev/financebert"
SENTIMENT_MODEL_PATH = os.getenv("SENTIFY_MODEL_PATH", "").strip()
SENTIMENT_MODEL_ID = (
    os.getenv("SENTIFY_MODEL_ID", DEFAULT_SENTIMENT_MODEL_ID).strip()
    or DEFAULT_SENTIMENT_MODEL_ID
)
SENTIMENT_MODEL_REVISION = os.getenv("SENTIFY_MODEL_REVISION", "").strip()
SENTIMENT_MODEL_LOCAL_FILES_ONLY = _get_bool_env(
    "SENTIFY_MODEL_LOCAL_FILES_ONLY"
)
