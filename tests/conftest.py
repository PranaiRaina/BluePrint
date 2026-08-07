"""Skip tests that call real APIs unless RUN_LIVE_TESTS is set.

~95% of this suite's wall time was live LLM/Wolfram/Finnhub calls, and tests
whose assertion is a model's judgment flake by construction. Mark those with
`pytest.mark.live` (usually `pytestmark = pytest.mark.live` at module level).

    pytest                      # offline only, ~10s
    RUN_LIVE_TESTS=1 pytest     # everything, ~2min
    pytest -m live              # collect only the live set
"""

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_LIVE_TESTS"):
        return
    skip_live = pytest.mark.skip(reason="live API test; set RUN_LIVE_TESTS=1 to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
