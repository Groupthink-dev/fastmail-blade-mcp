"""Tests for FastmailClient."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestClientInit:
    def test_init_with_token(self, mock_jmapc_client):
        with patch.dict("os.environ", {"FASTMAIL_API_TOKEN": "fmu1-testtoken"}):
            from fastmail_blade_mcp.client import FastmailClient

            client = FastmailClient(api_token="fmu1-testtoken")
            assert client.account_id == "u12345"

    def test_init_without_token(self):
        with patch.dict("os.environ", {}, clear=True):
            from fastmail_blade_mcp.client import AuthError, FastmailClient

            with pytest.raises(AuthError, match="FASTMAIL_API_TOKEN"):
                FastmailClient()

    def test_init_from_env(self, mock_jmapc_client):
        with patch.dict("os.environ", {"FASTMAIL_API_TOKEN": "fmu1-envtoken"}):
            from fastmail_blade_mcp.client import FastmailClient

            client = FastmailClient()
            assert client.account_id == "u12345"


class TestSessionInfo:
    def test_get_session_info(self, client, mock_jmapc_client):
        info = client.get_session_info()
        assert info["account_id"] == "u12345"
        assert "capabilities" in info


class TestGetMailboxes:
    def test_get_mailboxes(self, client, mock_jmapc_client, sample_mailboxes):
        mock_response = MagicMock()
        mock_response.data = sample_mailboxes
        mock_jmapc_client.request.return_value = mock_response

        result = client.get_mailboxes()
        assert len(result) == 4
        assert result[0].name == "Inbox"


class TestGetEmail:
    def test_get_email(self, client, mock_jmapc_client, sample_email_full):
        mock_response = MagicMock()
        mock_response.data = [sample_email_full]
        mock_jmapc_client.request.return_value = mock_response

        result = client.get_email("M001")
        assert result.id == "M001"
        assert result.subject == "Meeting notes"

    def test_get_email_not_found(self, client, mock_jmapc_client):
        mock_response = MagicMock()
        mock_response.data = []
        mock_jmapc_client.request.return_value = mock_response

        from fastmail_blade_mcp.client import NotFoundError

        with pytest.raises(NotFoundError):
            client.get_email("nonexistent")


class TestSearchEmails:
    def test_search_by_sender(self, client, mock_jmapc_client, sample_emails):
        query_response = MagicMock()
        query_response.ids = ["M001"]
        query_response.total = 1

        get_response = MagicMock()
        get_response.data = [sample_emails[0]]

        mock_jmapc_client.request.side_effect = [query_response, get_response]

        emails, total = client.search_emails(from_addr="alice@example.com")
        assert len(emails) == 1
        assert total == 1

    def test_search_no_results(self, client, mock_jmapc_client):
        query_response = MagicMock()
        query_response.ids = []
        query_response.total = 0
        mock_jmapc_client.request.return_value = query_response

        emails, total = client.search_emails(subject="nonexistent")
        assert len(emails) == 0
        assert total == 0


class TestGetThread:
    def test_get_thread(self, client, mock_jmapc_client, sample_thread, sample_thread_obj):
        thread_response = MagicMock()
        thread_response.data = [sample_thread_obj]

        get_response = MagicMock()
        get_response.data = sample_thread

        mock_jmapc_client.request.side_effect = [thread_response, get_response]

        result = client.get_thread("T001")
        assert len(result) == 2

    def test_get_thread_not_found(self, client, mock_jmapc_client):
        thread_response = MagicMock()
        thread_response.data = []
        mock_jmapc_client.request.return_value = thread_response

        from fastmail_blade_mcp.client import NotFoundError

        with pytest.raises(NotFoundError):
            client.get_thread("nonexistent")


class TestGetIdentities:
    def test_get_identities(self, client, mock_jmapc_client, sample_identities):
        mock_response = MagicMock()
        mock_response.data = sample_identities
        mock_jmapc_client.request.return_value = mock_response

        result = client.get_identities()
        assert len(result) == 2
        assert result[0].email == "piers@fastmail.com"


class TestMaskedEmails:
    def test_get_masked_emails(self, client, mock_jmapc_client, sample_masked_emails):
        mock_response = MagicMock()
        mock_response.data = sample_masked_emails
        mock_jmapc_client.request.return_value = mock_response

        result = client.get_masked_emails()
        assert len(result) == 2

    def test_filter_by_state(self, client, mock_jmapc_client, sample_masked_emails):
        mock_response = MagicMock()
        mock_response.data = sample_masked_emails
        mock_jmapc_client.request.return_value = mock_response

        result = client.get_masked_emails(state="enabled")
        assert len(result) == 1
        assert result[0].email == "abc123@fastmail.com"

    def test_filter_by_domain(self, client, mock_jmapc_client, sample_masked_emails):
        mock_response = MagicMock()
        mock_response.data = sample_masked_emails
        mock_jmapc_client.request.return_value = mock_response

        result = client.get_masked_emails(for_domain="netflix")
        assert len(result) == 1

    def test_create_masked_email(self, client, mock_jmapc_client):
        from jmapc.fastmail import MaskedEmail, MaskedEmailState

        created_mask = MaskedEmail(
            id="me-new",
            email="new123@fastmail.com",
            state=MaskedEmailState.ENABLED,
            for_domain="test.com",
        )
        mock_response = MagicMock()
        mock_response.created = {"new": created_mask}
        mock_jmapc_client.request.return_value = mock_response

        result = client.create_masked_email(for_domain="test.com", description="Test")
        assert result.email == "new123@fastmail.com"


class TestEmailState:
    def test_get_email_state(self, client, mock_jmapc_client):
        mock_response = MagicMock()
        mock_response.state = "s123456"
        mock_response.data = []
        mock_jmapc_client.request.return_value = mock_response

        result = client.get_email_state()
        assert result == "s123456"

    def test_get_email_state_none(self, client, mock_jmapc_client):
        mock_response = MagicMock()
        mock_response.state = None
        mock_response.data = []
        mock_jmapc_client.request.return_value = mock_response

        from fastmail_blade_mcp.client import FastmailError

        with pytest.raises(FastmailError, match="state"):
            client.get_email_state()


class TestEmailChanges:
    def test_get_email_changes(self, client, mock_jmapc_client):
        mock_response = MagicMock()
        mock_response.old_state = "s100"
        mock_response.new_state = "s200"
        mock_response.has_more_changes = False
        mock_response.created = ["M001", "M002"]
        mock_response.updated = ["M003"]
        mock_response.destroyed = []
        mock_jmapc_client.request.return_value = mock_response

        result = client.get_email_changes("s100")
        assert result["old_state"] == "s100"
        assert result["new_state"] == "s200"
        assert result["has_more_changes"] is False
        assert result["created"] == ["M001", "M002"]
        assert result["updated"] == ["M003"]
        assert result["destroyed"] == []

    def test_get_email_changes_with_max(self, client, mock_jmapc_client):
        mock_response = MagicMock()
        mock_response.old_state = "s100"
        mock_response.new_state = "s150"
        mock_response.has_more_changes = True
        mock_response.created = ["M001"]
        mock_response.updated = []
        mock_response.destroyed = []
        mock_jmapc_client.request.return_value = mock_response

        result = client.get_email_changes("s100", max_changes=10)
        assert result["has_more_changes"] is True

    def test_cannot_calculate_changes(self, client, mock_jmapc_client):
        from jmapc import ClientError

        mock_jmapc_client.request.side_effect = ClientError(
            "cannotCalculateChanges",
            result=[],
        )

        from fastmail_blade_mcp.client import CannotCalculateChangesError

        with pytest.raises(CannotCalculateChangesError):
            client.get_email_changes("ancient_state")


class TestErrorClassification:
    def test_auth_error(self):
        from fastmail_blade_mcp.client import AuthError, _classify_error

        err = _classify_error("Unauthorized access")
        assert isinstance(err, AuthError)

    def test_not_found_error(self):
        from fastmail_blade_mcp.client import NotFoundError, _classify_error

        err = _classify_error("Resource not found")
        assert isinstance(err, NotFoundError)

    def test_rate_limit_error(self):
        from fastmail_blade_mcp.client import RateLimitError, _classify_error

        err = _classify_error("Rate limit exceeded")
        assert isinstance(err, RateLimitError)

    def test_connection_error(self):
        from fastmail_blade_mcp.client import ConnectionError, _classify_error

        err = _classify_error("Connection timeout")
        assert isinstance(err, ConnectionError)

    def test_cannot_calculate_changes_error(self):
        from fastmail_blade_mcp.client import CannotCalculateChangesError, _classify_error

        err = _classify_error("cannotCalculateChanges: state too old")
        assert isinstance(err, CannotCalculateChangesError)

    def test_generic_error(self):
        from fastmail_blade_mcp.client import FastmailError, _classify_error

        err = _classify_error("Something went wrong")
        assert type(err) is FastmailError


class TestTokenScrubbing:
    def test_scrub_token(self):
        from fastmail_blade_mcp.client import _scrub_token

        text = "Error with token fmu1-abcdef12345 in request"
        result = _scrub_token(text)
        assert "fmu1-abcdef12345" not in result
        assert "fmu1-****" in result

    def test_scrub_no_token(self):
        from fastmail_blade_mcp.client import _scrub_token

        text = "Normal error message"
        assert _scrub_token(text) == text


class TestWriteGate:
    def test_write_disabled_by_default(self):
        with patch.dict("os.environ", {}, clear=True):
            from fastmail_blade_mcp.models import is_write_enabled

            assert not is_write_enabled()

    def test_write_enabled(self):
        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            from fastmail_blade_mcp.models import is_write_enabled

            assert is_write_enabled()

    def test_require_write_disabled(self):
        with patch.dict("os.environ", {}, clear=True):
            from fastmail_blade_mcp.models import require_write

            result = require_write()
            assert result is not None
            assert "disabled" in result.lower() or "FASTMAIL_WRITE_ENABLED" in result

    def test_require_write_enabled(self):
        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            from fastmail_blade_mcp.models import require_write

            assert require_write() is None
