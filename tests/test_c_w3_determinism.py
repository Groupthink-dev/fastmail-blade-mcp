"""DD-338 Phase C Wave 3 — `_meta` envelope determinism + integration harness.

Asserts that the 5 promoted Fastmail tools (`mail_search`, `mail_threads`,
`mail_snippets`, `mail_changes`, `masked_list`) emit a canonical
``\n\n_meta: {...}`` JSON-tail envelope and that across N=3 repeat
invocations with a frozen mocked upstream the tail is byte-equal once
the non-deterministic ``latency_ms`` field is stripped.
"""

from __future__ import annotations

import json
import re
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_META_RE = re.compile(r"\n\n(_meta: \{.*\})$", re.DOTALL)


def _split_payload_and_meta(result: str) -> tuple[str, dict[str, Any]]:
    """Split a tool result into (payload, parsed_meta_dict).

    Asserts the canonical separator and prefix are present.
    """
    assert "\n\n_meta: " in result, f"missing canonical \\n\\n_meta: separator in: {result!r}"
    payload, _, tail = result.rpartition("\n\n")
    assert tail.startswith("_meta: ")
    meta = json.loads(tail[len("_meta: ") :])
    return payload, meta


def _strip_latency(meta: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of meta with the non-deterministic ``latency_ms`` removed."""
    out = dict(meta)
    out.pop("latency_ms", None)
    return out


@pytest.fixture
def mock_client():
    """Patch ``_get_client`` to return a mock FastmailClient."""
    with patch("fastmail_blade_mcp.server._get_client") as mock_get:
        client = MagicMock()
        mock_get.return_value = client
        yield client


# ===========================================================================
# mail_search
# ===========================================================================


class TestMailSearchMetaEnvelope:
    async def test_emits_canonical_envelope(self, mock_client, sample_emails):
        from fastmail_blade_mcp.server import mail_search

        mock_client.search_emails.return_value = (sample_emails, 42)
        result = await mail_search(from_addr="alice@example.com", limit=20)

        _, meta = _split_payload_and_meta(result)
        assert meta["matched_total"] == 42
        assert meta["returned"] == len(sample_emails)
        assert "from_addr=alice@example.com" in meta["filtered_by"]
        assert "limit=20" in meta["filtered_by"]
        # Sorted alphabetically.
        assert meta["filtered_by"] == sorted(meta["filtered_by"])
        assert isinstance(meta["latency_ms"], int)
        assert meta["latency_ms"] >= 0
        # Empty optional fields are absent.
        assert "redactions" not in meta
        assert "next_cursor" not in meta

    async def test_filtered_by_includes_all_applied_filters(self, mock_client, sample_emails):
        from fastmail_blade_mcp.server import mail_search

        mock_client.search_emails.return_value = (sample_emails, 2)
        result = await mail_search(
            from_addr="alice@example.com",
            to_addr="bob@example.com",
            subject="meeting",
            after="2026-01-01",
            in_mailbox="mb-inbox",
            has_keyword="$flagged",
            limit=10,
        )
        _, meta = _split_payload_and_meta(result)
        keys = {f.split("=")[0] for f in meta["filtered_by"]}
        assert {"from_addr", "to_addr", "subject", "after", "in_mailbox", "has_keyword", "limit"} <= keys

    async def test_n3_deterministic_after_latency_strip(self, mock_client, sample_emails):
        from fastmail_blade_mcp.server import mail_search

        mock_client.search_emails.return_value = (sample_emails, 42)
        results = [await mail_search(from_addr="alice@example.com", limit=20) for _ in range(3)]
        stripped = []
        for r in results:
            payload, meta = _split_payload_and_meta(r)
            stripped.append((payload, _strip_latency(meta)))
        # All payloads + (sans-latency) meta dicts equal.
        assert all(s == stripped[0] for s in stripped[1:])


# ===========================================================================
# mail_threads
# ===========================================================================


class TestMailThreadsMetaEnvelope:
    async def test_emits_canonical_envelope(self, mock_client, sample_thread):
        from fastmail_blade_mcp.server import mail_threads

        mock_client.get_thread.return_value = sample_thread
        result = await mail_threads(id="T001")

        _, meta = _split_payload_and_meta(result)
        assert meta["matched_total"] == len(sample_thread)
        assert meta["returned"] == len(sample_thread)
        assert meta["filtered_by"] == ["thread_id=T001"]
        assert isinstance(meta["latency_ms"], int)

    async def test_n3_deterministic(self, mock_client, sample_thread):
        from fastmail_blade_mcp.server import mail_threads

        mock_client.get_thread.return_value = sample_thread
        results = [await mail_threads(id="T001") for _ in range(3)]
        stripped = [(_split_payload_and_meta(r)[0], _strip_latency(_split_payload_and_meta(r)[1])) for r in results]
        assert all(s == stripped[0] for s in stripped[1:])


# ===========================================================================
# mail_snippets
# ===========================================================================


class TestMailSnippetsMetaEnvelope:
    async def test_emits_canonical_envelope(self, mock_client, sample_snippets, sample_emails):
        from fastmail_blade_mcp.server import mail_snippets

        mock_client.get_snippets.return_value = (sample_snippets, sample_emails, 5)
        result = await mail_snippets(subject="quarterly", limit=20)

        _, meta = _split_payload_and_meta(result)
        assert meta["matched_total"] == 5
        assert meta["returned"] == len(sample_snippets)
        assert "subject=quarterly" in meta["filtered_by"]
        assert "limit=20" in meta["filtered_by"]
        assert meta["filtered_by"] == sorted(meta["filtered_by"])

    async def test_n3_deterministic(self, mock_client, sample_snippets, sample_emails):
        from fastmail_blade_mcp.server import mail_snippets

        mock_client.get_snippets.return_value = (sample_snippets, sample_emails, 5)
        results = [await mail_snippets(subject="quarterly", limit=20) for _ in range(3)]
        stripped = [(_split_payload_and_meta(r)[0], _strip_latency(_split_payload_and_meta(r)[1])) for r in results]
        assert all(s == stripped[0] for s in stripped[1:])


# ===========================================================================
# mail_changes — Option C (OQ-3) semantics
# ===========================================================================


class TestMailChangesMetaEnvelope:
    async def test_emits_canonical_envelope_clean(self, mock_client):
        from fastmail_blade_mcp.server import mail_changes

        mock_client.get_email_changes.return_value = {
            "old_state": "s100",
            "new_state": "s200",
            "has_more_changes": False,
            "created": ["M001", "M002"],
            "updated": ["M003"],
            "destroyed": [],
        }
        result = await mail_changes(since_state="s100abcdef1234", max_changes=100)

        _, meta = _split_payload_and_meta(result)
        # Option C: matched_total = returned = sum(created + updated + destroyed)
        assert meta["matched_total"] == 3
        assert meta["returned"] == 3
        # since_state truncated to 12 chars; max_changes always declared.
        assert "since_state=s100abcdef12" in meta["filtered_by"]
        assert "max_changes=100" in meta["filtered_by"]
        # Sorted.
        assert meta["filtered_by"] == sorted(meta["filtered_by"])
        # has_more_changes=False -> no redactions key.
        assert "redactions" not in meta
        # next_cursor surfaces new_state.
        assert meta["next_cursor"] == "s200"

    async def test_more_changes_redaction(self, mock_client):
        from fastmail_blade_mcp.server import mail_changes

        mock_client.get_email_changes.return_value = {
            "old_state": "s100",
            "new_state": "s101",
            "has_more_changes": True,
            "created": ["M001"],
            "updated": [],
            "destroyed": [],
        }
        result = await mail_changes(since_state="s100", max_changes=10)
        _, meta = _split_payload_and_meta(result)
        assert meta["redactions"] == ["more_changes_available"]
        assert meta["matched_total"] == 1

    async def test_empty_changes_aggregate_zero(self, mock_client):
        from fastmail_blade_mcp.server import mail_changes

        mock_client.get_email_changes.return_value = {
            "old_state": "s100",
            "new_state": "s100",
            "has_more_changes": False,
            "created": [],
            "updated": [],
            "destroyed": [],
        }
        result = await mail_changes(since_state="s100", max_changes=100)
        _, meta = _split_payload_and_meta(result)
        assert meta["matched_total"] == 0
        assert meta["returned"] == 0

    async def test_n3_deterministic(self, mock_client):
        from fastmail_blade_mcp.server import mail_changes

        mock_client.get_email_changes.return_value = {
            "old_state": "s100",
            "new_state": "s200",
            "has_more_changes": True,
            "created": ["M001", "M002"],
            "updated": ["M003"],
            "destroyed": ["M004"],
        }
        results = [await mail_changes(since_state="s100abcdef1234", max_changes=50) for _ in range(3)]
        stripped = [(_split_payload_and_meta(r)[0], _strip_latency(_split_payload_and_meta(r)[1])) for r in results]
        assert all(s == stripped[0] for s in stripped[1:])


# ===========================================================================
# masked_list
# ===========================================================================


class TestMaskedListMetaEnvelope:
    async def test_emits_canonical_envelope(self, mock_client, sample_masked_emails):
        from fastmail_blade_mcp.server import masked_list

        mock_client.get_masked_emails.return_value = sample_masked_emails
        result = await masked_list(state="enabled", for_domain="example.com", limit=20)

        _, meta = _split_payload_and_meta(result)
        # JMAP has no pre-LIMIT count; matched_total tracks list length.
        assert meta["matched_total"] == len(sample_masked_emails)
        # returned == min(matched_total, limit).
        assert meta["returned"] == min(len(sample_masked_emails), 20)
        assert "state=enabled" in meta["filtered_by"]
        assert "for_domain=example.com" in meta["filtered_by"]
        assert "limit=20" in meta["filtered_by"]
        assert meta["filtered_by"] == sorted(meta["filtered_by"])

    async def test_no_filters_omit_null_keys(self, mock_client, sample_masked_emails):
        from fastmail_blade_mcp.server import masked_list

        mock_client.get_masked_emails.return_value = sample_masked_emails
        result = await masked_list(limit=20)
        _, meta = _split_payload_and_meta(result)
        keys = {f.split("=")[0] for f in meta["filtered_by"]}
        assert "limit" in keys
        assert "state" not in keys
        assert "for_domain" not in keys

    async def test_n3_deterministic(self, mock_client, sample_masked_emails):
        from fastmail_blade_mcp.server import masked_list

        mock_client.get_masked_emails.return_value = sample_masked_emails
        results = [await masked_list(state="enabled", limit=20) for _ in range(3)]
        stripped = [(_split_payload_and_meta(r)[0], _strip_latency(_split_payload_and_meta(r)[1])) for r in results]
        assert all(s == stripped[0] for s in stripped[1:])


# ===========================================================================
# Error returns: NO _meta envelope (OQ-7)
# ===========================================================================


class TestErrorReturnsNoEnvelope:
    async def test_mail_search_error_has_no_envelope(self, mock_client):
        from fastmail_blade_mcp.client import FastmailError
        from fastmail_blade_mcp.server import mail_search

        mock_client.search_emails.side_effect = FastmailError("Connection failed")
        result = await mail_search(from_addr="alice@example.com")
        assert "\n\n_meta: " not in result

    async def test_mail_changes_cannot_calculate_has_no_envelope(self, mock_client):
        from fastmail_blade_mcp.client import CannotCalculateChangesError
        from fastmail_blade_mcp.server import mail_changes

        mock_client.get_email_changes.side_effect = CannotCalculateChangesError("State too old")
        result = await mail_changes(since_state="ancient")
        assert "\n\n_meta: " not in result


# ===========================================================================
# Regex assembler probe — ensure shape matches the canonical regex
# ===========================================================================


class TestAssemblerRegexMatch:
    async def test_meta_line_matches_canonical_regex(self, mock_client, sample_emails):
        from fastmail_blade_mcp.server import mail_search

        mock_client.search_emails.return_value = (sample_emails, 1)
        result = await mail_search(from_addr="alice@example.com")
        m = _META_RE.search(result)
        assert m is not None
        # The captured group must round-trip as JSON.
        meta = json.loads(m.group(1)[len("_meta: ") :])
        assert "matched_total" in meta
