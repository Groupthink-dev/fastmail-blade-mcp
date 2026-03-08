"""E2E test fixtures — require live Fastmail account.

Gated by FASTMAIL_E2E=1 environment variable.
Requires FASTMAIL_API_TOKEN to be set with a valid token.
"""

from __future__ import annotations

import os

import pytest

from fastmail_blade_mcp.client import FastmailClient


def pytest_collection_modifyitems(config, items):
    """Skip e2e tests unless FASTMAIL_E2E=1."""
    if os.environ.get("FASTMAIL_E2E") != "1":
        skip = pytest.mark.skip(reason="FASTMAIL_E2E=1 not set")
        for item in items:
            if "e2e" in item.nodeid:
                item.add_marker(skip)


@pytest.fixture(scope="session")
def live_client() -> FastmailClient:
    """Create a live FastmailClient from environment token."""
    token = os.environ.get("FASTMAIL_API_TOKEN")
    if not token:
        pytest.skip("FASTMAIL_API_TOKEN not set")
    client = FastmailClient(api_token=token)
    # Health check
    info = client.get_session_info()
    assert info.get("account_id"), "Session health check failed"
    return client
