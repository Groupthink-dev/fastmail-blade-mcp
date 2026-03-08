"""E2E read-only tests against live Fastmail account.

Run with: FASTMAIL_E2E=1 make test-e2e
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
class TestSessionInfo:
    def test_fastmail_info(self, live_client):
        info = live_client.get_session_info()
        assert info["account_id"]
        assert info.get("email")
        assert len(info.get("capabilities", [])) > 0


@pytest.mark.e2e
class TestMailboxes:
    def test_get_mailboxes(self, live_client):
        mailboxes = live_client.get_mailboxes()
        assert len(mailboxes) > 0
        names = [mb.name for mb in mailboxes]
        assert "Inbox" in names or any("inbox" in (mb.role or "") for mb in mailboxes)


@pytest.mark.e2e
class TestIdentities:
    def test_get_identities(self, live_client):
        identities = live_client.get_identities()
        assert len(identities) > 0
        assert identities[0].email


@pytest.mark.e2e
class TestEmailSearch:
    def test_search_recent(self, live_client):
        emails, total = live_client.search_emails(limit=5)
        # May be empty if new account, but should not error
        assert isinstance(emails, list)
        assert isinstance(total, int)

    def test_search_with_limit(self, live_client):
        emails, total = live_client.search_emails(limit=3)
        assert len(emails) <= 3


@pytest.mark.e2e
class TestEmailRead:
    def test_read_first_email(self, live_client):
        emails, total = live_client.search_emails(limit=1)
        if not emails:
            pytest.skip("No emails in account")
        email = live_client.get_email(emails[0].id)
        assert email.id
        assert email.subject is not None


@pytest.mark.e2e
class TestPushStatus:
    def test_check_push_status(self, live_client):
        status = live_client.check_push_status()
        assert "available" in status
