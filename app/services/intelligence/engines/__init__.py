"""v4 intelligence engines (portfolio + market).

Engines here are pure, deterministic, fail-soft helpers. Each `analyse(...)`
method must:
- accept the existing `_analysis_context` dict shape
- return its corresponding schema (or a sentinel-filled default)
- never raise

All free-text output must pass `compliance_filter.sanitize_text`.
"""
