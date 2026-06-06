"""Tests for HTTP transport authentication hardening."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def reset_bearer_cache():
    import fastmail_blade_mcp.auth as auth

    auth._BEARER_TOKEN = None
    auth._BEARER_CHECKED = False
    yield
    auth._BEARER_TOKEN = None
    auth._BEARER_CHECKED = False


def test_loopback_http_may_run_without_bearer():
    from fastmail_blade_mcp.auth import require_secure_http

    with patch.dict("os.environ", {}, clear=True):
        require_secure_http("127.0.0.1")


def test_non_loopback_http_requires_bearer():
    from fastmail_blade_mcp.auth import require_secure_http

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="FASTMAIL_MCP_API_TOKEN"):
            require_secure_http("0.0.0.0")


def test_non_loopback_http_allows_configured_bearer():
    from fastmail_blade_mcp.auth import require_secure_http

    with patch.dict("os.environ", {"FASTMAIL_MCP_API_TOKEN": "secret"}, clear=True):
        require_secure_http("0.0.0.0")
