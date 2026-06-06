"""E2E masked email tests against live Fastmail account.

Run with: FASTMAIL_E2E=1 make test-e2e

These tests are READ-ONLY — no masked emails are created or modified.
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
class TestMaskedEmailList:
    def test_list_masked_emails(self, live_client):
        """List masked emails — should not error even if empty."""
        masks = live_client.get_masked_emails()
        assert isinstance(masks, list)

    def test_client_returns_full_list_no_truncation(self, live_client):
        """get_masked_emails returns the FULL filtered list (D1 regression).

        The client must not truncate — truncation is the presentation layer's
        job. If the client capped the list, masked_list's matched_total would
        collapse to the display limit and hide that more masks exist.
        """
        masks = live_client.get_masked_emails()
        assert isinstance(masks, list)
        # The harden account holds well over 20 masks; a client cap would show ~20.
        # We don't hard-code a count, but assert the param was actually removed.
        import inspect

        sig = inspect.signature(live_client.get_masked_emails)
        assert "limit" not in sig.parameters, "client must not truncate masked lists"

    def test_filter_by_state(self, live_client):
        """Filter by state — should not error."""
        masks = live_client.get_masked_emails(state="enabled")
        assert isinstance(masks, list)
        for mask in masks:
            assert mask.state.value == "enabled"
