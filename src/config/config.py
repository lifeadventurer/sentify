import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export ") :].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


_load_dotenv(BASE_DIR / ".env")


def _get_bool_env(var_name: str, default: bool = False) -> bool:
    value = os.getenv(var_name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int_env(var_name: str, default: int) -> int:
    value = os.getenv(var_name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _get_cache_retention_env(var_name: str, freshness_ttl: int) -> int:
    retention_ttl = _get_int_env(var_name, freshness_ttl)
    return max(retention_ttl, freshness_ttl)


TOP_COMPANIES_COUNT = 10000
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
UTC_DIFFERENCE = 8
CPU_COUNT = 2
MAX_NEWS_LOOKBACK_DAYS = 60
SECONDS_PER_DAY = 86400
SENTIFY_CACHE_DIR = Path(
    os.getenv("SENTIFY_CACHE_DIR", BASE_DIR / ".cache" / "sentify")
)
NEWS_LIST_CACHE_TTL_SECONDS = _get_int_env(
    "SENTIFY_NEWS_LIST_CACHE_TTL_SECONDS", 900
)
NEWS_ARTICLE_CACHE_TTL_SECONDS = _get_int_env(
    "SENTIFY_NEWS_ARTICLE_CACHE_TTL_SECONDS",
    MAX_NEWS_LOOKBACK_DAYS * SECONDS_PER_DAY,
)
SENTIMENT_CACHE_TTL_SECONDS = _get_int_env(
    "SENTIFY_SENTIMENT_CACHE_TTL_SECONDS",
    MAX_NEWS_LOOKBACK_DAYS * SECONDS_PER_DAY,
)
DEFAULT_CACHE_RETENTION_SECONDS = MAX_NEWS_LOOKBACK_DAYS * SECONDS_PER_DAY
NEWS_LIST_CACHE_RETENTION_SECONDS = _get_cache_retention_env(
    "SENTIFY_NEWS_LIST_CACHE_RETENTION_SECONDS",
    max(NEWS_LIST_CACHE_TTL_SECONDS, DEFAULT_CACHE_RETENTION_SECONDS),
)
NEWS_ARTICLE_CACHE_RETENTION_SECONDS = _get_cache_retention_env(
    "SENTIFY_NEWS_ARTICLE_CACHE_RETENTION_SECONDS",
    max(NEWS_ARTICLE_CACHE_TTL_SECONDS, DEFAULT_CACHE_RETENTION_SECONDS),
)
SENTIMENT_CACHE_RETENTION_SECONDS = _get_cache_retention_env(
    "SENTIFY_SENTIMENT_CACHE_RETENTION_SECONDS",
    max(SENTIMENT_CACHE_TTL_SECONDS, DEFAULT_CACHE_RETENTION_SECONDS),
)

DEFAULT_SENTIMENT_MODEL_ID = "marcev/financebert"
OFFLINE_MODE = _get_bool_env("SENTIFY_OFFLINE_MODE")
SENTIMENT_MODEL_PATH = os.getenv("SENTIFY_MODEL_PATH", "").strip()
SENTIMENT_MODEL_ID = (
    os.getenv("SENTIFY_MODEL_ID", DEFAULT_SENTIMENT_MODEL_ID).strip()
    or DEFAULT_SENTIMENT_MODEL_ID
)
SENTIMENT_MODEL_REVISION = os.getenv("SENTIFY_MODEL_REVISION", "").strip()
SENTIMENT_MODEL_LOCAL_FILES_ONLY = _get_bool_env(
    "SENTIFY_MODEL_LOCAL_FILES_ONLY"
)
