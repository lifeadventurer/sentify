# Changelog

## 1.0.0 - 2026-03-21

First official Sentify release.

### Overview

Sentify is a Flask web application for turning stock-related news into an
actionable Buy, Hold, or Sell recommendation. It combines Yahoo Finance news
retrieval, transformer-based sentiment analysis, article-level weighting, and
an interactive dashboard into a single workflow.

### Core capabilities

- Search by company name or ticker symbol.
- Autocomplete suggestions for company names and ticker symbols.
- Fetch and review recent Yahoo Finance news for the selected company.
- Score article sentiment and summarize the result into a Buy, Hold, or Sell
  recommendation with a confidence score.
- Display per-article publish timing, sentiment output, and article details in
  the dashboard.

### Recommendation controls

- Adjustable news lookback window from the main dashboard.
- Recommendation tuning controls for recency weighting.
- Recommendation tuning controls for article content-length weighting.
- Client-side recalculation support so weighting changes can update the
  recommendation view without reprocessing cached sentiment unnecessarily.

### Dashboard and user experience

- TradingView chart embed alongside the recommendation summary.
- Search suggestion dropdown and improved company selection flow.
- Clear cache action from the dashboard.
- Recommendation summary cards and confidence display in the main interface.

### Caching and fallback behavior

- Cached Yahoo news list responses.
- Cached article body retrieval.
- Cached sentiment results keyed to the active model identity.
- Stale-cache fallback when live Yahoo requests fail.
- Cached-sentiment fallback when live model loading is unavailable.
- Offline mode for local-only operation with stale cache reuse.
- Cache retention and cleanup on startup.

### Configuration and deployment behavior

- Environment-variable based configuration for model selection, cache paths,
  cache TTLs, and weighting controls.
- Local `.env` support.
- Debug mode disabled by default for normal app runs.

### Quality and reliability

- Structured runtime logging in key fallback and failure paths.
- Runtime hardening for cache cleanup and Yahoo response handling.
- Automated unit test coverage for recommendation logic, fallback behavior,
  search behavior, and cache handling.
- GitHub Actions CI coverage for both lint/pre-commit checks and the unittest
  suite.
