"""DD-338 Phase B.1.b — sort-before-return determinism harness.

Asserts N=5 byte-identical output across shuffled-input invocations for each
of the 2 multi-record fastmail tools, plus per-tool sort-key invariance tests.

Tools covered:
    - fastmail_identities  (sort key: id asc)
    - mail_mailboxes       (sort key: sort_order asc — None at tail via 9999 sentinel —
                            then name asc, then id asc)

JMAP `sortOrder` attribute on `jmapc.Mailbox`: verified at branch checkout
2026-05-23 — the attribute is named `sort_order` (Python snake_case) with
default value `0` per `jmapc.models.mailbox.Mailbox`. No fallback needed.
"""

from __future__ import annotations

import random
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from jmapc import Identity, Mailbox


@pytest.fixture
def mock_client() -> Any:
    with patch("fastmail_blade_mcp.server._get_client") as mock_get:
        client = MagicMock()
        mock_get.return_value = client
        yield client


# ---------------------------------------------------------------------------
# Shuffled fixtures
# ---------------------------------------------------------------------------


def _shuffled_identities() -> list[Identity]:
    base = [
        Identity(
            id="id-z",
            name="Zeta",
            email="zeta@fastmail.com",
            reply_to=None,
            bcc=None,
            text_signature=None,
            html_signature=None,
            may_delete=True,
        ),
        Identity(
            id="id-a",
            name="Alpha",
            email="alpha@fastmail.com",
            reply_to=None,
            bcc=None,
            text_signature=None,
            html_signature=None,
            may_delete=True,
        ),
        Identity(
            id="id-m",
            name="Mu",
            email="mu@fastmail.com",
            reply_to=None,
            bcc=None,
            text_signature=None,
            html_signature=None,
            may_delete=True,
        ),
    ]
    random.shuffle(base)
    return base


def _shuffled_mailboxes() -> list[Mailbox]:
    base = [
        Mailbox(id="mb-2", name="Archive", role=None, sort_order=20, total_emails=1, unread_emails=0),
        Mailbox(id="mb-1", name="Inbox", role="inbox", sort_order=10, total_emails=10, unread_emails=2),
        Mailbox(id="mb-4", name="Junk", role=None, sort_order=None, total_emails=3, unread_emails=0),  # type: ignore[arg-type]
        Mailbox(id="mb-3", name="Sent", role="sent", sort_order=10, total_emails=5, unread_emails=0),
    ]
    random.shuffle(base)
    return base


# ---------------------------------------------------------------------------
# fastmail_identities
# ---------------------------------------------------------------------------


class TestFastmailIdentitiesDeterminism:
    async def test_n5_byte_identical(self, mock_client: Any) -> None:
        from fastmail_blade_mcp.server import fastmail_identities

        outputs: list[str] = []
        for _ in range(5):
            mock_client.get_identities.return_value = _shuffled_identities()
            outputs.append(await fastmail_identities())
        assert all(out == outputs[0] for out in outputs), "N=5 outputs diverge"

    async def test_sort_key_honoured(self, mock_client: Any) -> None:
        from fastmail_blade_mcp.server import fastmail_identities

        mock_client.get_identities.return_value = _shuffled_identities()
        result = await fastmail_identities()
        # id asc: id-a < id-m < id-z
        pos_a = result.find("id=id-a")
        pos_m = result.find("id=id-m")
        pos_z = result.find("id=id-z")
        assert 0 <= pos_a < pos_m < pos_z, f"sort key not honoured: a={pos_a} m={pos_m} z={pos_z}"

    async def test_empty_input(self, mock_client: Any) -> None:
        from fastmail_blade_mcp.server import fastmail_identities

        mock_client.get_identities.return_value = []
        result = await fastmail_identities()
        assert "No identities" in result


# ---------------------------------------------------------------------------
# mail_mailboxes
# ---------------------------------------------------------------------------


class TestMailMailboxesDeterminism:
    async def test_n5_byte_identical(self, mock_client: Any) -> None:
        from fastmail_blade_mcp.server import mail_mailboxes

        outputs: list[str] = []
        for _ in range(5):
            mock_client.get_mailboxes.return_value = _shuffled_mailboxes()
            outputs.append(await mail_mailboxes())
        assert all(out == outputs[0] for out in outputs), "N=5 outputs diverge"

    async def test_sort_key_honoured(self, mock_client: Any) -> None:
        from fastmail_blade_mcp.server import mail_mailboxes

        mock_client.get_mailboxes.return_value = _shuffled_mailboxes()
        result = await mail_mailboxes()
        # Expected:
        #   sort_order=10: Inbox (mb-1), Sent (mb-3) — tied on sort_order → name asc → Inbox first
        #   sort_order=20: Archive (mb-2)
        #   sort_order=None (→9999): Junk (mb-4)
        pos_inbox = result.find("Inbox")
        pos_sent = result.find("Sent")
        pos_archive = result.find("Archive")
        pos_junk = result.find("Junk")
        assert 0 <= pos_inbox < pos_sent < pos_archive < pos_junk, (
            f"sort key not honoured: inbox={pos_inbox} sent={pos_sent} archive={pos_archive} junk={pos_junk}"
        )

    async def test_none_sort_order_at_tail(self, mock_client: Any) -> None:
        from fastmail_blade_mcp.server import mail_mailboxes

        # All sort_order=None — falls back to name asc then id asc.
        mailboxes = [
            Mailbox(id="mb-z", name="Z-folder", sort_order=None),  # type: ignore[arg-type]
            Mailbox(id="mb-a", name="A-folder", sort_order=None),  # type: ignore[arg-type]
            Mailbox(id="mb-m", name="M-folder", sort_order=None),  # type: ignore[arg-type]
        ]
        random.shuffle(mailboxes)
        mock_client.get_mailboxes.return_value = mailboxes
        result = await mail_mailboxes()
        pos_a = result.find("A-folder")
        pos_m = result.find("M-folder")
        pos_z = result.find("Z-folder")
        assert 0 <= pos_a < pos_m < pos_z

    async def test_empty_input(self, mock_client: Any) -> None:
        from fastmail_blade_mcp.server import mail_mailboxes

        mock_client.get_mailboxes.return_value = []
        result = await mail_mailboxes()
        assert "No mailboxes" in result
