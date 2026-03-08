"""Shared fixtures for Fastmail Blade MCP tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from jmapc import Email, EmailAddress, EmailBodyPart, EmailBodyValue, Identity, Mailbox, SearchSnippet, Thread
from jmapc.fastmail import MaskedEmail, MaskedEmailState


@pytest.fixture
def mock_jmapc_client():
    """Patch jmapc.Client.create_with_api_token to return a mock."""
    with patch("fastmail_blade_mcp.client.Client") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.create_with_api_token.return_value = mock_instance
        mock_instance.account_id = "u12345"
        mock_capabilities = MagicMock()
        mock_capabilities.urns = {"urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"}
        mock_instance.jmap_session = MagicMock(
            username="test@fastmail.com",
            capabilities=mock_capabilities,
            event_source_url="https://api.fastmail.com/jmap/event/?types={types}&closeafter={closeafter}&ping={ping}",
        )
        yield mock_instance


@pytest.fixture
def client(mock_jmapc_client):
    """Create a FastmailClient with mocked jmapc."""
    with patch.dict("os.environ", {"FASTMAIL_API_TOKEN": "fmu1-testtoken"}):
        from fastmail_blade_mcp.client import FastmailClient

        return FastmailClient(api_token="fmu1-testtoken")


@pytest.fixture
def sample_mailboxes() -> list[Mailbox]:
    """Sample mailbox data."""
    return [
        Mailbox(id="mb-inbox", name="Inbox", role="inbox", total_emails=1234, unread_emails=56),
        Mailbox(id="mb-sent", name="Sent", role="sent", total_emails=890, unread_emails=0),
        Mailbox(id="mb-drafts", name="Drafts", role="drafts", total_emails=3, unread_emails=3),
        Mailbox(id="mb-trash", name="Trash", role="trash", total_emails=42, unread_emails=0),
    ]


@pytest.fixture
def sample_emails() -> list[Email]:
    """Sample email list data."""
    return [
        Email(
            id="M001",
            thread_id="T001",
            mailbox_ids={"mb-inbox": True},
            keywords={"$seen": True},
            size=4200,
            received_at=datetime(2026, 3, 7, 10, 30, tzinfo=UTC),
            subject="Meeting notes",
            mail_from=[EmailAddress(name="Alice", email="alice@example.com")],
            to=[EmailAddress(name="Bob", email="bob@example.com")],
            preview="Here are the meeting notes from today...",
        ),
        Email(
            id="M002",
            thread_id="T002",
            mailbox_ids={"mb-inbox": True},
            keywords={"$seen": True, "$flagged": True},
            size=1100,
            received_at=datetime(2026, 3, 6, 14, 0, tzinfo=UTC),
            subject="Re: Project update",
            mail_from=[EmailAddress(name="Bob", email="bob@example.com")],
            to=[EmailAddress(name="Alice", email="alice@example.com")],
            preview="The project is on track...",
        ),
    ]


@pytest.fixture
def sample_email_full() -> Email:
    """Sample full email with body."""
    return Email(
        id="M001",
        thread_id="T001",
        mailbox_ids={"mb-inbox": True},
        keywords={"$seen": True},
        size=4200,
        received_at=datetime(2026, 3, 7, 10, 30, tzinfo=UTC),
        subject="Meeting notes",
        mail_from=[EmailAddress(name="Alice", email="alice@example.com")],
        to=[EmailAddress(name="Bob", email="bob@example.com")],
        cc=[EmailAddress(email="charlie@example.com")],
        message_id=["<msg001@example.com>"],
        text_body=[EmailBodyPart(part_id="1", type="text/plain")],
        body_values={"1": EmailBodyValue(value="Here are the meeting notes from today.\n\nBest regards,\nAlice")},
    )


@pytest.fixture
def sample_thread() -> list[Email]:
    """Sample thread with multiple emails."""
    return [
        Email(
            id="M001",
            thread_id="T001",
            received_at=datetime(2026, 3, 5, 9, 0, tzinfo=UTC),
            subject="Meeting tomorrow",
            mail_from=[EmailAddress(name="Alice", email="alice@example.com")],
            text_body=[EmailBodyPart(part_id="1", type="text/plain")],
            body_values={"1": EmailBodyValue(value="Let's meet at 2pm.")},
        ),
        Email(
            id="M002",
            thread_id="T001",
            received_at=datetime(2026, 3, 5, 10, 0, tzinfo=UTC),
            subject="Re: Meeting tomorrow",
            mail_from=[EmailAddress(name="Bob", email="bob@example.com")],
            text_body=[EmailBodyPart(part_id="1", type="text/plain")],
            body_values={"1": EmailBodyValue(value="Sounds good, see you then.")},
        ),
    ]


@pytest.fixture
def sample_identities() -> list[Identity]:
    """Sample sender identities."""
    return [
        Identity(
            id="id-primary",
            name="Piers",
            email="piers@fastmail.com",
            reply_to=None,
            bcc=None,
            text_signature=None,
            html_signature=None,
            may_delete=True,
        ),
        Identity(
            id="id-work",
            name="Piers Work",
            email="piers@work.com",
            reply_to=None,
            bcc=None,
            text_signature=None,
            html_signature=None,
            may_delete=True,
        ),
    ]


@pytest.fixture
def sample_masked_emails() -> list[MaskedEmail]:
    """Sample masked email data."""
    return [
        MaskedEmail(
            id="me-001",
            email="abc123@fastmail.com",
            state=MaskedEmailState.ENABLED,
            for_domain="netflix.com",
            description="Netflix account",
            created_at=datetime(2026, 1, 15, tzinfo=UTC),
            last_message_at=datetime(2026, 3, 1, tzinfo=UTC),
        ),
        MaskedEmail(
            id="me-002",
            email="def456@fastmail.com",
            state=MaskedEmailState.DISABLED,
            for_domain="other.com",
            description="Old service",
            created_at=datetime(2025, 6, 1, tzinfo=UTC),
        ),
    ]


@pytest.fixture
def sample_snippets() -> list[SearchSnippet]:
    """Sample search snippets."""
    return [
        SearchSnippet(
            email_id="M001",
            subject="Meeting notes",
            preview="discussed the <mark>project</mark> timeline",
        ),
        SearchSnippet(
            email_id="M002",
            subject="Re: Budget review",
            preview="the <mark>project</mark> budget is on track",
        ),
    ]


@pytest.fixture
def sample_thread_obj() -> Thread:
    """Sample Thread object."""
    return Thread(id="T001", email_ids=["M001", "M002"])
