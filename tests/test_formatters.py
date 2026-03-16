"""Tests for token-efficient formatters."""

from __future__ import annotations

from jmapc import Email

from fastmail_blade_mcp.formatters import (
    format_changes,
    format_email_body,
    format_email_list,
    format_identity_list,
    format_mailbox_list,
    format_masked_email_list,
    format_push_events,
    format_push_status,
    format_search_snippets,
    format_session_info,
    format_thread,
    truncate_body,
)

# ===========================================================================
# format_mailbox_list
# ===========================================================================


class TestFormatMailboxList:
    def test_empty(self):
        assert format_mailbox_list([]) == "No mailboxes found."

    def test_with_mailboxes(self, sample_mailboxes):
        result = format_mailbox_list(sample_mailboxes)
        assert "Inbox" in result
        assert "(1234/56)" in result
        assert "[inbox]" in result
        assert "Sent" in result
        assert "Drafts" in result
        assert "Trash" in result

    def test_mailbox_with_id(self, sample_mailboxes):
        result = format_mailbox_list(sample_mailboxes)
        assert "id=mb-inbox" in result


# ===========================================================================
# format_email_list
# ===========================================================================


class TestFormatEmailList:
    def test_empty(self):
        assert format_email_list([]) == "No emails found."

    def test_with_emails(self, sample_emails):
        result = format_email_list(sample_emails)
        assert "Alice" in result
        assert "Meeting notes" in result
        assert "M001" in result

    def test_truncation(self, sample_emails):
        result = format_email_list(sample_emails, total=50, limit=1)
        assert "49 more" in result

    def test_no_truncation_when_within_limit(self, sample_emails):
        result = format_email_list(sample_emails, limit=10)
        assert "more" not in result


# ===========================================================================
# format_email_body
# ===========================================================================


class TestFormatEmailBody:
    def test_full_email(self, sample_email_full):
        result = format_email_body(sample_email_full)
        assert "From: Alice <alice@example.com>" in result
        assert "To: Bob <bob@example.com>" in result
        assert "Cc: charlie@example.com" in result
        assert "Subject: Meeting notes" in result
        assert "meeting notes from today" in result
        assert "ID: M001" in result
        assert "Thread: T001" in result

    def test_no_body(self):
        email = Email(id="M999", subject="Empty")
        result = format_email_body(email)
        assert "(no body)" in result

    def test_flags_shown(self, sample_email_full):
        result = format_email_body(sample_email_full)
        assert "Flags:" in result
        assert "$seen" in result


# ===========================================================================
# format_thread
# ===========================================================================


class TestFormatThread:
    def test_empty(self):
        assert format_thread([]) == "Empty thread."

    def test_with_messages(self, sample_thread):
        result = format_thread(sample_thread)
        assert "[1/2]" in result
        assert "[2/2]" in result
        assert "Alice" in result or "alice@example.com" in result
        assert "Bob" in result or "bob@example.com" in result
        assert "Let's meet at 2pm" in result


# ===========================================================================
# format_search_snippets
# ===========================================================================


class TestFormatSearchSnippets:
    def test_empty(self):
        assert format_search_snippets([], []) == "No results found."

    def test_with_snippets(self, sample_snippets, sample_emails):
        result = format_search_snippets(sample_snippets, sample_emails)
        assert "project" in result.lower()
        assert "Meeting notes" in result or "Budget review" in result

    def test_truncation(self, sample_snippets, sample_emails):
        result = format_search_snippets(sample_snippets, sample_emails, total=50, limit=1)
        assert "49 more" in result


# ===========================================================================
# format_masked_email_list
# ===========================================================================


class TestFormatMaskedEmailList:
    def test_empty(self):
        assert format_masked_email_list([]) == "No masked emails found."

    def test_with_masks(self, sample_masked_emails):
        result = format_masked_email_list(sample_masked_emails)
        assert "abc123@fastmail.com" in result
        assert "enabled" in result
        assert "netflix.com" in result
        assert "Netflix account" in result
        assert "def456@fastmail.com" in result
        assert "disabled" in result

    def test_truncation(self, sample_masked_emails):
        result = format_masked_email_list(sample_masked_emails, total=100, limit=1)
        assert "99 more" in result


# ===========================================================================
# format_session_info
# ===========================================================================


class TestFormatSessionInfo:
    def test_basic(self):
        info = {
            "account_id": "u12345",
            "email": "test@fastmail.com",
            "capabilities": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
        }
        result = format_session_info(info)
        assert "Account: test@fastmail.com" in result
        assert "Account ID: u12345" in result
        assert "urn:ietf:params:jmap:core" in result

    def test_empty_info(self):
        result = format_session_info({})
        assert result == "{}"


# ===========================================================================
# format_identity_list
# ===========================================================================


class TestFormatIdentityList:
    def test_empty(self):
        assert format_identity_list([]) == "No identities found."

    def test_with_identities(self, sample_identities):
        result = format_identity_list(sample_identities)
        assert "Piers <piers@fastmail.com>" in result
        assert "id=id-primary" in result
        assert "Piers Work <piers@work.com>" in result


# ===========================================================================
# format_push_events / format_push_status
# ===========================================================================


# ===========================================================================
# format_changes
# ===========================================================================


class TestFormatChanges:
    def test_basic(self):
        changes = {
            "old_state": "s100",
            "new_state": "s200",
            "has_more_changes": False,
            "created": ["M001", "M002", "M003"],
            "updated": ["M004"],
            "destroyed": [],
        }
        result = format_changes(changes)
        assert "s100 → s200" in result
        assert "Has more: false" in result
        assert "Created (3)" in result
        assert "M001, M002, M003" in result
        assert "Updated (1)" in result
        assert "Destroyed (0)" in result

    def test_empty_changes(self):
        changes = {
            "old_state": "s100",
            "new_state": "s100",
            "has_more_changes": False,
            "created": [],
            "updated": [],
            "destroyed": [],
        }
        result = format_changes(changes)
        assert "Created (0):" in result
        assert "Updated (0):" in result

    def test_has_more(self):
        changes = {
            "old_state": "s100",
            "new_state": "s150",
            "has_more_changes": True,
            "created": ["M001"],
            "updated": [],
            "destroyed": [],
        }
        result = format_changes(changes)
        assert "Has more: true" in result

    def test_truncation_at_20(self):
        ids = [f"M{i:03d}" for i in range(25)]
        changes = {
            "old_state": "s1",
            "new_state": "s2",
            "has_more_changes": False,
            "created": ids,
            "updated": [],
            "destroyed": [],
        }
        result = format_changes(changes)
        assert "Created (25)" in result
        assert "+5 more" in result


class TestFormatPushEvents:
    def test_empty(self):
        assert format_push_events([]) == "No events received within timeout."

    def test_with_events(self):
        events = [
            {"id": "evt1", "changed": {"u12345": {"Email": "state123", "Mailbox": "state456"}}},
        ]
        result = format_push_events(events)
        assert "Email: state123" in result
        assert "Mailbox: state456" in result


class TestFormatPushStatus:
    def test_available(self):
        result = format_push_status({"available": True, "url": "https://example.com/events"})
        assert "available" in result
        assert "https://example.com/events" in result

    def test_not_available(self):
        result = format_push_status({"available": False})
        assert "not available" in result


# ===========================================================================
# truncate_body
# ===========================================================================


class TestTruncateBody:
    def test_short_text(self):
        assert truncate_body("hello") == "hello"

    def test_long_text(self):
        long_text = "x" * 60_000
        result = truncate_body(long_text, max_chars=50_000)
        assert len(result) < 60_000
        assert "truncated" in result
        assert "10000 more" in result
