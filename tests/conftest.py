import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests requiring running services",
    )


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("TEST_BASE_URL", "http://localhost:8000")
