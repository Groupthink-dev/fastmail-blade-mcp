"""Tests for MCP server tools."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fastmail_blade_mcp.client import FastmailError, NotFoundError


@pytest.fixture
def mock_client():
    """Patch _get_client to return a mock FastmailClient."""
    with patch("fastmail_blade_mcp.server._get_client") as mock_get:
        mock_fm = MagicMock()
        mock_get.return_value = mock_fm
        yield mock_fm


# ===========================================================================
# META TOOLS
# ===========================================================================


class TestFastmailInfo:
    async def test_success(self, mock_client):
        from fastmail_blade_mcp.server import fastmail_info

        mock_client.get_session_info.return_value = {
            "account_id": "u12345",
            "email": "test@fastmail.com",
            "capabilities": ["urn:ietf:params:jmap:core"],
        }
        result = await fastmail_info()
        assert "test@fastmail.com" in result
        assert "u12345" in result

    async def test_error(self, mock_client):
        from fastmail_blade_mcp.server import fastmail_info

        mock_client.get_session_info.side_effect = FastmailError("Connection failed")
        result = await fastmail_info()
        assert "Error:" in result


class TestFastmailIdentities:
    async def test_success(self, mock_client, sample_identities):
        from fastmail_blade_mcp.server import fastmail_identities

        mock_client.get_identities.return_value = sample_identities
        result = await fastmail_identities()
        assert "piers@fastmail.com" in result


# ===========================================================================
# EMAIL READ TOOLS
# ===========================================================================


class TestMailMailboxes:
    async def test_success(self, mock_client, sample_mailboxes):
        from fastmail_blade_mcp.server import mail_mailboxes

        mock_client.get_mailboxes.return_value = sample_mailboxes
        result = await mail_mailboxes()
        assert "Inbox" in result
        assert "(1234/56)" in result


class TestMailRead:
    async def test_success(self, mock_client, sample_email_full):
        from fastmail_blade_mcp.server import mail_read

        mock_client.get_email.return_value = sample_email_full
        result = await mail_read(id="M001")
        assert "Alice" in result
        assert "Meeting notes" in result
        assert "meeting notes from today" in result

    async def test_not_found(self, mock_client):
        from fastmail_blade_mcp.server import mail_read

        mock_client.get_email.side_effect = NotFoundError("Email not found")
        result = await mail_read(id="nonexistent")
        assert "Error:" in result


class TestMailSearch:
    async def test_success(self, mock_client, sample_emails):
        from fastmail_blade_mcp.server import mail_search

        mock_client.search_emails.return_value = (sample_emails, 2)
        result = await mail_search(from_addr="alice@example.com")
        assert "Meeting notes" in result

    async def test_no_results(self, mock_client):
        from fastmail_blade_mcp.server import mail_search

        mock_client.search_emails.return_value = ([], 0)
        result = await mail_search(subject="nonexistent")
        assert "No emails found" in result


class TestMailThreads:
    async def test_success(self, mock_client, sample_thread):
        from fastmail_blade_mcp.server import mail_threads

        mock_client.get_thread.return_value = sample_thread
        result = await mail_threads(id="T001")
        assert "[1/2]" in result
        assert "[2/2]" in result

    async def test_not_found(self, mock_client):
        from fastmail_blade_mcp.server import mail_threads

        mock_client.get_thread.side_effect = NotFoundError("Thread not found")
        result = await mail_threads(id="nonexistent")
        assert "Error:" in result


class TestMailSnippets:
    async def test_success(self, mock_client, sample_snippets, sample_emails):
        from fastmail_blade_mcp.server import mail_snippets

        mock_client.get_snippets.return_value = (sample_snippets, sample_emails, 2)
        result = await mail_snippets(body="project")
        assert "project" in result.lower()


# ===========================================================================
# EMAIL WRITE TOOLS (write-gated)
# ===========================================================================


class TestMailSend:
    async def test_write_disabled(self, mock_client):
        from fastmail_blade_mcp.server import mail_send

        with patch.dict("os.environ", {}, clear=True):
            result = await mail_send(to="bob@example.com", subject="Test", body="Hello")
            assert "Error:" in result
            assert "disabled" in result.lower() or "FASTMAIL_WRITE_ENABLED" in result

    async def test_write_enabled(self, mock_client):
        from fastmail_blade_mcp.server import mail_send

        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            mock_client.send_email.return_value = "sub-001"
            result = await mail_send(to="bob@example.com", subject="Test", body="Hello")
            assert "Sent" in result
            assert "sub-001" in result


class TestMailReply:
    async def test_write_disabled(self, mock_client):
        from fastmail_blade_mcp.server import mail_reply

        with patch.dict("os.environ", {}, clear=True):
            result = await mail_reply(id="M001", body="Thanks")
            assert "Error:" in result

    async def test_write_enabled(self, mock_client):
        from fastmail_blade_mcp.server import mail_reply

        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            mock_client.reply_to_email.return_value = "sub-002"
            result = await mail_reply(id="M001", body="Thanks")
            assert "Reply sent" in result


class TestMailMove:
    async def test_write_disabled(self, mock_client):
        from fastmail_blade_mcp.server import mail_move

        with patch.dict("os.environ", {}, clear=True):
            result = await mail_move(ids="M001", to_mailbox="mb-trash")
            assert "Error:" in result

    async def test_write_enabled(self, mock_client):
        from fastmail_blade_mcp.server import mail_move

        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            mock_client.move_emails.return_value = 1
            result = await mail_move(ids="M001", to_mailbox="mb-trash")
            assert "Moved 1" in result


class TestMailFlag:
    async def test_write_disabled(self, mock_client):
        from fastmail_blade_mcp.server import mail_flag

        with patch.dict("os.environ", {}, clear=True):
            result = await mail_flag(ids="M001")
            assert "Error:" in result

    async def test_set_flag(self, mock_client):
        from fastmail_blade_mcp.server import mail_flag

        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            mock_client.flag_emails.return_value = 1
            result = await mail_flag(ids="M001")
            assert "Set" in result
            assert "$flagged" in result

    async def test_clear_flag(self, mock_client):
        from fastmail_blade_mcp.server import mail_flag

        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            mock_client.flag_emails.return_value = 1
            result = await mail_flag(ids="M001", clear=True)
            assert "Cleared" in result


# ===========================================================================
# EMAIL MANAGE TOOLS
# ===========================================================================


class TestMailDelete:
    async def test_write_disabled(self, mock_client):
        from fastmail_blade_mcp.server import mail_delete

        with patch.dict("os.environ", {}, clear=True):
            result = await mail_delete(ids="M001")
            assert "Error:" in result

    async def test_move_to_trash(self, mock_client):
        from fastmail_blade_mcp.server import mail_delete

        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            mock_client.delete_emails.return_value = 1
            result = await mail_delete(ids="M001")
            assert "Trash" in result

    async def test_permanent_delete(self, mock_client):
        from fastmail_blade_mcp.server import mail_delete

        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            mock_client.delete_emails.return_value = 1
            result = await mail_delete(ids="M001", permanent=True)
            assert "Permanently" in result


class TestMailBulk:
    async def test_write_disabled(self, mock_client):
        from fastmail_blade_mcp.server import mail_bulk

        with patch.dict("os.environ", {}, clear=True):
            result = await mail_bulk(ids="M001,M002", action="mark_read")
            assert "Error:" in result

    async def test_mark_read(self, mock_client):
        from fastmail_blade_mcp.server import mail_bulk

        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            mock_client.bulk_action.return_value = 2
            result = await mail_bulk(ids="M001,M002", action="mark_read")
            assert "2" in result

    async def test_batch_limit(self, mock_client):
        from fastmail_blade_mcp.server import mail_bulk

        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            ids = ",".join([f"M{i:03d}" for i in range(60)])
            result = await mail_bulk(ids=ids, action="flag")
            assert "Maximum 50" in result


# ===========================================================================
# MASKED EMAIL TOOLS
# ===========================================================================


class TestMaskedList:
    async def test_success(self, mock_client, sample_masked_emails):
        from fastmail_blade_mcp.server import masked_list

        mock_client.get_masked_emails.return_value = sample_masked_emails
        result = await masked_list()
        assert "abc123@fastmail.com" in result
        assert "netflix.com" in result


class TestMaskedCreate:
    async def test_write_disabled(self, mock_client):
        from fastmail_blade_mcp.server import masked_create

        with patch.dict("os.environ", {}, clear=True):
            result = await masked_create(for_domain="test.com")
            assert "Error:" in result

    async def test_write_enabled(self, mock_client):
        from fastmail_blade_mcp.server import masked_create

        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            mock_mask = MagicMock()
            mock_mask.email = "new@fastmail.com"
            mock_mask.id = "me-new"
            mock_client.create_masked_email.return_value = mock_mask
            result = await masked_create(for_domain="test.com")
            assert "Created" in result
            assert "new@fastmail.com" in result


class TestMaskedUpdate:
    async def test_write_disabled(self, mock_client):
        from fastmail_blade_mcp.server import masked_update

        with patch.dict("os.environ", {}, clear=True):
            result = await masked_update(id="me-001", state="disabled")
            assert "Error:" in result

    async def test_write_enabled(self, mock_client):
        from fastmail_blade_mcp.server import masked_update

        with patch.dict("os.environ", {"FASTMAIL_WRITE_ENABLED": "true"}):
            mock_client.update_masked_email.return_value = {"id": "me-001", "state": "disabled"}
            result = await masked_update(id="me-001", state="disabled")
            assert "Updated" in result


# ===========================================================================
# PUSH TOOLS
# ===========================================================================


class TestPushSubscribe:
    async def test_no_events(self, mock_client):
        from fastmail_blade_mcp.server import push_subscribe

        mock_client.subscribe_push.return_value = []
        result = await push_subscribe(timeout=5)
        assert "No events" in result

    async def test_with_events(self, mock_client):
        from fastmail_blade_mcp.server import push_subscribe

        mock_client.subscribe_push.return_value = [{"id": "evt1", "changed": {"u12345": {"Email": "state123"}}}]
        result = await push_subscribe(timeout=5)
        assert "Email: state123" in result


class TestPushStatus:
    async def test_available(self, mock_client):
        from fastmail_blade_mcp.server import push_status

        mock_client.check_push_status.return_value = {
            "available": True,
            "url": "https://api.fastmail.com/events",
        }
        result = await push_status()
        assert "available" in result


# ===========================================================================
# Error handling
# ===========================================================================


class TestUnexpectedErrors:
    async def test_unexpected_error_in_read(self, mock_client):
        from fastmail_blade_mcp.server import mail_read

        mock_client.get_email.side_effect = RuntimeError("Unexpected")
        result = await mail_read(id="M001")
        assert "Error:" in result

    async def test_unexpected_error_in_search(self, mock_client):
        from fastmail_blade_mcp.server import mail_search

        mock_client.search_emails.side_effect = RuntimeError("Unexpected")
        result = await mail_search(subject="test")
        assert "Error:" in result

    async def test_unexpected_error_in_mailboxes(self, mock_client):
        from fastmail_blade_mcp.server import mail_mailboxes

        mock_client.get_mailboxes.side_effect = RuntimeError("Unexpected")
        result = await mail_mailboxes()
        assert "Error:" in result
