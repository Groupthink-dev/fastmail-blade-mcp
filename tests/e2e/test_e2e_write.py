"""E2E write tests against live Fastmail account.

Run with:
    FASTMAIL_E2E=1 FASTMAIL_WRITE_E2E=1 FASTMAIL_WRITE_ENABLED=true make test-e2e

These tests create disposable ``zz-`` resources and tear them down in ``finally``.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest


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
