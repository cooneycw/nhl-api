"""Cross-source validation for comparing data between different NHL data sources.

This package provides validators that compare data from different sources:
- JSON API vs HTML Reports (json_vs_html.py)

Example usage:
    from nhl_api.validation.cross_source import JSONvsHTMLValidator

    validator = JSONvsHTMLValidator()
    results = validator.validate_goals(pbp_goals, gs_goals)

    for result in results:
        if not result.passed:
            print(f"{result.severity}: {result.message}")
"""

from nhl_api.validation.cross_source.json_vs_html import JSONvsHTMLValidator

__all__ = [
    "JSONvsHTMLValidator",
]
