"""E2E write tests against live Fastmail account.

Run with:
    FASTMAIL_E2E=1 FASTMAIL_WRITE_E2E=1 FASTMAIL_WRITE_ENABLED=true make test-e2e

These tests create disposable ``zz-`` resources and tear them down in ``finally``.
"""

from __future__ import annotations

import os
import time
from uuid import uuid4

import jmapc
import pytest
from jmapc import Email, EmailAddress
from jmapc.methods import EmailSet


def _require_write() -> None:
    if os.environ.get("FASTMAIL_WRITE_E2E") != "1":
        pytest.skip("FASTMAIL_WRITE_E2E=1 not set")
    if os.environ.get("FASTMAIL_WRITE_ENABLED", "").lower() != "true":
        pytest.skip("FASTMAIL_WRITE_ENABLED=true not set")


def _create_throwaway_draft(client, subject: str) -> tuple[str, str]:
    """Create a disposable draft in Drafts (setup only — bypasses the blade API).

    Returns (email_id, drafts_mailbox_id).
    """
    drafts = client._get_drafts_mailbox_id()
    draft = Email(
        to=[EmailAddress(email="nobody@example.invalid")],
        subject=subject,
        keywords={"$draft": True},
        mailbox_ids={drafts: True},
        body_values={"body": jmapc.EmailBodyValue(value="zz throwaway")},
        text_body=[jmapc.EmailBodyPart(part_id="body", type="text/plain")],
    )
    resp = client._client.request(EmailSet(create={"d": draft}), raise_errors=True)
    created = resp.created["d"]
    return created.id, drafts


def _mbox_keys(client, email_id: str) -> set[str]:
    email = client.get_email(email_id)
    return set((email.mailbox_ids or {}).keys())


@pytest.mark.e2e
class TestMaskedEmailWrite:
    def test_create_then_delete_masked_email(self, live_client):
        """Create a disposable masked email alias, then mark it deleted."""
        if os.environ.get("FASTMAIL_WRITE_E2E") != "1":
            pytest.skip("FASTMAIL_WRITE_E2E=1 not set")
        if os.environ.get("FASTMAIL_WRITE_ENABLED", "").lower() != "true":
            pytest.skip("FASTMAIL_WRITE_ENABLED=true not set")

        suffix = uuid4().hex[:12]
        mask_id: str | None = None

        try:
            mask = live_client.create_masked_email(
                for_domain=f"zz-fastmail-blade-{suffix}.example.com",
                description=f"zz-fastmail-blade-mcp live write regression {suffix}",
                email_prefix=f"zz{suffix}",
            )
            mask_id = mask.id

            assert mask_id
            assert mask.email
            # Fastmail's MaskedEmail/set create response does not echo every
            # submitted field; id+email are the stable wire confirmation.
        finally:
            if mask_id:
                result = live_client.update_masked_email(mask_id, state="deleted")
                assert result["id"] == mask_id
                assert result["state"] == "deleted"


@pytest.mark.e2e
class TestMoveDeleteSemantics:
    """D2 (DD-385): move/delete must REMOVE the source mailbox, not just add.

    JMAP mailboxIds are additive — before the fix, ``move_emails`` only added
    the destination and ``delete_emails`` only added Trash, leaving the message
    in its original folder(s). These assertions fail against the unfixed code
    (the resulting key set would be a superset, e.g. ``{drafts, archive}``).
    """

    def test_move_is_a_true_move_and_delete_lands_only_in_trash(self, live_client):
        _require_write()
        subject = f"zz-harden-move-{uuid4().hex[:12]}"
        email_id: str | None = None
        try:
            email_id, drafts = _create_throwaway_draft(live_client, subject)
            assert _mbox_keys(live_client, email_id) == {drafts}

            archive = live_client._get_mailbox_id_by_role("archive")
            live_client.move_emails([email_id], archive)
            keys = _mbox_keys(live_client, email_id)
            assert keys == {archive}, f"move left message in extra mailboxes: {keys}"

            trash = live_client._get_trash_mailbox_id()
            live_client.delete_emails([email_id])  # to-Trash (non-permanent)
            keys = _mbox_keys(live_client, email_id)
            assert keys == {trash}, f"delete-to-Trash left message in extra mailboxes: {keys}"
        finally:
            if email_id:
                live_client.delete_emails([email_id], permanent=True)


@pytest.mark.e2e
class TestSendActuallySends:
    """D5 (DD-385): mail_send must report success and land the copy in Sent.

    Before the fix, the ``on_success_update_email`` patch used snake_case
    ``mailbox_ids/`` JSON pointers (invalid on the wire), so the submission
    succeeded but the draft→Sent transition failed: jmapc raised, the caller
    saw a generic error, and the sent copy was stranded in Drafts as ``$draft``
    — while the email actually went out. This test sends to an account-owned
    identity (internal loop) and asserts the copy is in Sent, not Drafts.
    """

    def test_send_succeeds_and_lands_in_sent_not_drafts(self, live_client):
        _require_write()
        marker = f"zz-harden-send-{uuid4().hex[:12]}"
        try:
            identities = live_client.get_identities()
            assert identities, "no sender identities"
            self_ident = identities[0]

            submission_id = live_client.send_email(
                to=[self_ident.email],
                subject=marker,
                body="zz harden-blade D5 regression",
                from_identity=self_ident.id,
            )
            # A real submission id is returned (not a raised error, not the
            # "submitted" fallback) — the send genuinely completed.
            assert submission_id and submission_id != "submitted"

            sent = live_client._get_sent_mailbox_id()
            drafts = live_client._get_drafts_mailbox_id()
            sent_copy = None
            for _ in range(15):
                emails, _ = live_client.search_emails(subject=marker, limit=20)
                for e in emails:
                    if sent in set((e.mailbox_ids or {}).keys()):
                        sent_copy = e
                        break
                if sent_copy:
                    break
                time.sleep(2)

            assert sent_copy is not None, "sent message never appeared in Sent (stranded in Drafts?)"
            keys = set((sent_copy.mailbox_ids or {}).keys())
            assert drafts not in keys, f"sent copy still in Drafts: {keys}"
            assert "$draft" not in (sent_copy.keywords or {}), "sent copy still flagged $draft"
        finally:
            emails, _ = live_client.search_emails(subject=marker, limit=50)
            stale = [e.id for e in emails if marker in (e.subject or "")]
            if stale:
                live_client.delete_emails(stale, permanent=True)
