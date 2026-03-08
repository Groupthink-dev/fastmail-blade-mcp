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

    def test_list_with_limit(self, live_client):
        masks = live_client.get_masked_emails(limit=5)
        assert len(masks) <= 5

    def test_filter_by_state(self, live_client):
        """Filter by state — should not error."""
        masks = live_client.get_masked_emails(state="enabled", limit=5)
        assert isinstance(masks, list)
        for mask in masks:
            assert mask.state.value == "enabled"
