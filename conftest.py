import os
import tempfile

import pytest


def pytest_configure(config):
    if not config.getoption("--basetemp"):
        base = os.environ.get("IGRIS_PYTEST_BASETEMP")
        if not base:
            base = os.path.join(tempfile.gettempdir(), "igris_pytest")
        config.option.basetemp = base
