"""Fastmail JMAP client wrapper.

Wraps ``jmapc.Client`` with typed exceptions, pattern-based error classification,
and convenience methods for each tool category. All methods are synchronous —
the server wraps them with ``asyncio.to_thread()``.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import jmapc
from jmapc import (
    Client,
    ClientError,
    Comparator,
    Email,
    EmailAddress,
    EmailQueryFilterCondition,
    EmailSubmission,
    EventSourceConfig,
    Identity,
    Mailbox,
    SearchSnippet,
    Thread,
)
from jmapc.fastmail import (
    MaskedEmail,
    MaskedEmailGet,
    MaskedEmailSet,
    MaskedEmailState,
)
from jmapc.methods import (
    EmailGet,
    EmailQuery,
    EmailSet,
    EmailSubmissionSet,
    IdentityGet,
    MailboxGet,
    SearchSnippetGet,
    ThreadGet,
)

from fastmail_blade_mcp.models import (
    EMAIL_LIST_PROPERTIES,
    EMAIL_READ_PROPERTIES,
    JMAP_HOST,
    MAX_BATCH_SIZE,
    MAX_PUSH_TIMEOUT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FastmailError(Exception):
    """Base exception for Fastmail client errors."""

    def __init__(self, message: str, details: str = "") -> None:
        super().__init__(message)
        self.details = details


class AuthError(FastmailError):
    """Authentication failed — invalid or expired token."""


class NotFoundError(FastmailError):
    """Requested resource (email, mailbox, masked email) not found."""


class RateLimitError(FastmailError):
    """Rate limit exceeded — back off and retry."""


class ConnectionError(FastmailError):  # noqa: A001
    """Cannot connect to Fastmail API."""


class WriteDisabledError(FastmailError):
    """Write operation attempted but FASTMAIL_WRITE_ENABLED is not true."""


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

_ERROR_PATTERNS: list[tuple[str, type[FastmailError]]] = [
    ("unauthorized", AuthError),
    ("authentication", AuthError),
    ("invalid credentials", AuthError),
    ("forbidden", AuthError),
    ("not found", NotFoundError),
    ("does not exist", NotFoundError),
    ("no such", NotFoundError),
    ("rate limit", RateLimitError),
    ("too many requests", RateLimitError),
    ("connection", ConnectionError),
    ("timeout", ConnectionError),
    ("unreachable", ConnectionError),
]


def _classify_error(message: str) -> FastmailError:
    """Map error message to a typed exception."""
    lower = message.lower()
    for pattern, exc_cls in _ERROR_PATTERNS:
        if pattern in lower:
            return exc_cls(message)
    return FastmailError(message)


def _scrub_token(text: str) -> str:
    """Remove API tokens from text to prevent leakage in logs/output."""
    return re.sub(r"fmu1-[a-zA-Z0-9]+", "fmu1-****", text)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class FastmailClient:
    """JMAP client wrapper for Fastmail.

    Wraps ``jmapc.Client`` with typed exceptions and convenience methods.
    All methods are synchronous — the MCP server's ``_run()`` helper wraps them
    in ``asyncio.to_thread()`` to avoid blocking the event loop.

    Args:
        api_token: Fastmail API token. Defaults to ``FASTMAIL_API_TOKEN`` env var.
        host: JMAP host. Defaults to ``api.fastmail.com``.
    """

    def __init__(
        self,
        api_token: str | None = None,
        host: str = JMAP_HOST,
    ) -> None:
        token = api_token or os.environ.get("FASTMAIL_API_TOKEN", "")
        if not token:
            raise AuthError("FASTMAIL_API_TOKEN is not set")
        self._client = Client.create_with_api_token(host=host, api_token=token)
        self._account_id: str | None = None
        logger.info("FastmailClient initialised for host=%s", host)

    @property
    def account_id(self) -> str:
        """Primary account ID (lazy-fetched from session)."""
        if self._account_id is None:
            self._account_id = self._client.account_id
        return self._account_id

    def _request(self, method: Any, **kwargs: Any) -> Any:
        """Execute a JMAP method with error handling."""
        try:
            return self._client.request(method, raise_errors=True, **kwargs)
        except ClientError as e:
            msg = _scrub_token(str(e))
            raise _classify_error(msg) from e
        except Exception as e:
            msg = _scrub_token(str(e))
            raise _classify_error(msg) from e

    # -------------------------------------------------------------------
    # Meta
    # -------------------------------------------------------------------

    def get_session_info(self) -> dict[str, Any]:
        """Get account info, capabilities, and limits from the JMAP session."""
        session = self._client.jmap_session
        return {
            "account_id": self.account_id,
            "email": session.username,
            "capabilities": list(session.capabilities.urns) if session.capabilities else [],
        }

    def get_identities(self) -> list[Identity]:
        """Get sender identities."""
        response = self._request(IdentityGet(ids=None))
        return list(response.data) if response.data else []

    # -------------------------------------------------------------------
    # Mailboxes
    # -------------------------------------------------------------------

    def get_mailboxes(self) -> list[Mailbox]:
        """Get all mailboxes with counts."""
        response = self._request(MailboxGet(ids=None))
        return list(response.data) if response.data else []

    # -------------------------------------------------------------------
    # Email Read
    # -------------------------------------------------------------------

    def get_email(self, email_id: str, html: bool = False) -> Email:
        """Get a single email by ID with full content."""
        properties = list(EMAIL_READ_PROPERTIES)
        response = self._request(
            EmailGet(
                ids=[email_id],
                properties=properties,
                fetch_text_body_values=True,
                fetch_html_body_values=html,
                max_body_value_bytes=256_000,
            )
        )
        if not response.data:
            raise NotFoundError(f"Email not found: {email_id}")
        email: Email = response.data[0]
        return email

    def search_emails(
        self,
        from_addr: str | None = None,
        to_addr: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        after: str | None = None,
        before: str | None = None,
        in_mailbox: str | None = None,
        has_keyword: str | None = None,
        not_keyword: str | None = None,
        limit: int = 20,
    ) -> tuple[list[Email], int]:
        """Search emails with filters. Returns (emails, total_count)."""
        filter_condition = EmailQueryFilterCondition(
            mail_from=from_addr,
            to=to_addr,
            header=["Subject", subject] if subject else None,
            body=body,
            after=datetime.fromisoformat(after).replace(tzinfo=UTC) if after else None,
            before=datetime.fromisoformat(before).replace(tzinfo=UTC) if before else None,
            in_mailbox=in_mailbox,
            has_keyword=has_keyword,
            not_keyword=not_keyword,
        )
        query_response = self._request(
            EmailQuery(
                filter=filter_condition,
                sort=[Comparator(property="receivedAt", is_ascending=False)],
                limit=limit,
                calculate_total=True,
            )
        )
        ids = query_response.ids or []
        total = query_response.total or len(ids)
        if not ids:
            return [], total

        get_response = self._request(
            EmailGet(
                ids=ids,
                properties=EMAIL_LIST_PROPERTIES,
                fetch_text_body_values=False,
            )
        )
        return list(get_response.data) if get_response.data else [], total

    def get_thread(self, thread_id: str) -> list[Email]:
        """Get all emails in a thread, ordered chronologically."""
        thread_response = self._request(ThreadGet(ids=[thread_id]))
        if not thread_response.data:
            raise NotFoundError(f"Thread not found: {thread_id}")
        thread: Thread = thread_response.data[0]
        email_ids = thread.email_ids
        if not email_ids:
            return []

        get_response = self._request(
            EmailGet(
                ids=email_ids,
                properties=EMAIL_LIST_PROPERTIES + ["textBody", "bodyValues"],
                fetch_text_body_values=True,
                max_body_value_bytes=10_000,
            )
        )
        emails = list(get_response.data) if get_response.data else []
        emails.sort(key=lambda e: e.received_at or datetime.min.replace(tzinfo=UTC))
        return emails

    def get_snippets(
        self,
        from_addr: str | None = None,
        subject: str | None = None,
        body: str | None = None,
        after: str | None = None,
        before: str | None = None,
        in_mailbox: str | None = None,
        limit: int = 20,
    ) -> tuple[list[SearchSnippet], list[Email], int]:
        """Search with highlighted snippets. Returns (snippets, emails, total)."""
        filter_condition = EmailQueryFilterCondition(
            mail_from=from_addr,
            header=["Subject", subject] if subject else None,
            body=body,
            after=datetime.fromisoformat(after).replace(tzinfo=UTC) if after else None,
            before=datetime.fromisoformat(before).replace(tzinfo=UTC) if before else None,
            in_mailbox=in_mailbox,
        )
        query_response = self._request(
            EmailQuery(
                filter=filter_condition,
                sort=[Comparator(property="receivedAt", is_ascending=False)],
                limit=limit,
                calculate_total=True,
            )
        )
        ids = query_response.ids or []
        total = query_response.total or len(ids)
        if not ids:
            return [], [], total

        snippet_response = self._request(
            SearchSnippetGet(
                ids=ids,
                filter=filter_condition,
            )
        )
        snippets = list(snippet_response.data) if snippet_response.data else []

        get_response = self._request(
            EmailGet(
                ids=ids,
                properties=["id", "subject", "from", "receivedAt"],
                fetch_text_body_values=False,
            )
        )
        emails = list(get_response.data) if get_response.data else []
        return snippets, emails, total

    # -------------------------------------------------------------------
    # Email Write
    # -------------------------------------------------------------------

    def send_email(
        self,
        to: list[str],
        subject: str,
        body: str,
        from_identity: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> str:
        """Send an email. Returns submission ID."""
        identity_id = from_identity or self._get_default_identity_id()

        to_addrs = [EmailAddress(email=addr) for addr in to]
        cc_addrs = [EmailAddress(email=addr) for addr in cc] if cc else None
        bcc_addrs = [EmailAddress(email=addr) for addr in bcc] if bcc else None

        identities = self.get_identities()
        from_addr = None
        for ident in identities:
            if ident.id == identity_id:
                from_addr = [EmailAddress(name=ident.name, email=ident.email)]
                break
        if not from_addr:
            from_addr = to_addrs[:1]

        draft = Email(
            mail_from=from_addr,
            to=to_addrs,
            cc=cc_addrs,
            bcc=bcc_addrs,
            subject=subject,
            keywords={"$draft": True},
            mailbox_ids={self._get_drafts_mailbox_id(): True},
            body_values={"body": jmapc.EmailBodyValue(value=body)},
            text_body=[jmapc.EmailBodyPart(part_id="body", type="text/plain")],
        )

        create_response = self._request(EmailSet(create={"draft": draft}))
        if not create_response.created or "draft" not in create_response.created:
            raise FastmailError("Failed to create draft email")
        created_email = create_response.created["draft"]
        email_id = created_email.id if created_email else None
        if not email_id:
            raise FastmailError("Draft created but no ID returned")

        submission = EmailSubmission(
            identity_id=identity_id,
            email_id=email_id,
        )
        sub_response = self._request(
            EmailSubmissionSet(
                create={"send": submission},
                on_success_update_email={
                    "#send": {
                        "keywords/$draft": None,
                        f"mailbox_ids/{self._get_sent_mailbox_id()}": True,
                        f"mailbox_ids/{self._get_drafts_mailbox_id()}": None,
                    }
                },
            )
        )
        if sub_response.created and "send" in sub_response.created:
            created_sub = sub_response.created["send"]
            return created_sub.id if created_sub else "submitted"
        return "submitted"

    def reply_to_email(
        self,
        email_id: str,
        body: str,
        reply_all: bool = False,
        from_identity: str | None = None,
    ) -> str:
        """Reply to an email. Returns submission ID."""
        original = self.get_email(email_id)
        identity_id = from_identity or self._get_default_identity_id()

        identities = self.get_identities()
        from_addr = None
        for ident in identities:
            if ident.id == identity_id:
                from_addr = [EmailAddress(name=ident.name, email=ident.email)]
                break

        to_addrs = list(original.reply_to or original.mail_from or [])
        cc_addrs = None
        if reply_all:
            all_recipients = list(original.to or []) + list(original.cc or [])
            my_emails = {ident.email for ident in identities}
            cc_addrs = [addr for addr in all_recipients if addr.email not in my_emails]

        subject = original.subject or ""
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        references = list(original.references or [])
        if original.message_id:
            references.extend(original.message_id)
        in_reply_to = original.message_id

        draft = Email(
            mail_from=from_addr,
            to=to_addrs,
            cc=cc_addrs,
            subject=subject,
            in_reply_to=in_reply_to,
            references=references if references else None,
            thread_id=original.thread_id,
            keywords={"$draft": True},
            mailbox_ids={self._get_drafts_mailbox_id(): True},
            body_values={"body": jmapc.EmailBodyValue(value=body)},
            text_body=[jmapc.EmailBodyPart(part_id="body", type="text/plain")],
        )

        create_response = self._request(EmailSet(create={"reply": draft}))
        if not create_response.created or "reply" not in create_response.created:
            raise FastmailError("Failed to create reply draft")
        created_email = create_response.created["reply"]
        reply_email_id = created_email.id if created_email else None
        if not reply_email_id:
            raise FastmailError("Reply draft created but no ID returned")

        submission = EmailSubmission(
            identity_id=identity_id,
            email_id=reply_email_id,
        )
        sub_response = self._request(
            EmailSubmissionSet(
                create={"send": submission},
                on_success_update_email={
                    "#send": {
                        "keywords/$draft": None,
                        f"mailbox_ids/{self._get_sent_mailbox_id()}": True,
                        f"mailbox_ids/{self._get_drafts_mailbox_id()}": None,
                    }
                },
            )
        )
        if sub_response.created and "send" in sub_response.created:
            created_sub = sub_response.created["send"]
            return created_sub.id if created_sub else "submitted"
        return "submitted"

    def move_emails(self, ids: list[str], to_mailbox: str, from_mailbox: str | None = None) -> int:
        """Move emails to a mailbox. Returns count moved."""
        update: dict[str, dict[str, Any]] = {}
        for eid in ids[:MAX_BATCH_SIZE]:
            patch: dict[str, Any] = {f"mailboxIds/{to_mailbox}": True}
            if from_mailbox:
                patch[f"mailboxIds/{from_mailbox}"] = None
            update[eid] = patch

        self._request(EmailSet(update=update))
        return len(update)

    def flag_emails(self, ids: list[str], keyword: str = "$flagged", clear: bool = False) -> int:
        """Flag or unflag emails. Returns count affected."""
        update: dict[str, dict[str, Any]] = {}
        for eid in ids[:MAX_BATCH_SIZE]:
            if clear:
                update[eid] = {f"keywords/{keyword}": None}
            else:
                update[eid] = {f"keywords/{keyword}": True}

        self._request(EmailSet(update=update))
        return len(update)

    # -------------------------------------------------------------------
    # Email Manage
    # -------------------------------------------------------------------

    def delete_emails(self, ids: list[str], permanent: bool = False) -> int:
        """Delete emails. Moves to Trash by default, permanent destroys."""
        if permanent:
            self._request(EmailSet(destroy=ids[:MAX_BATCH_SIZE]))
            return min(len(ids), MAX_BATCH_SIZE)
        return self.move_emails(ids, self._get_trash_mailbox_id())

    def bulk_action(
        self,
        ids: list[str],
        action: str,
        target_mailbox: str | None = None,
    ) -> int:
        """Perform bulk action on emails. Returns count affected."""
        capped = ids[:MAX_BATCH_SIZE]
        if action == "mark_read":
            return self.flag_emails(capped, keyword="$seen", clear=False)
        elif action == "mark_unread":
            return self.flag_emails(capped, keyword="$seen", clear=True)
        elif action == "flag":
            return self.flag_emails(capped, keyword="$flagged", clear=False)
        elif action == "unflag":
            return self.flag_emails(capped, keyword="$flagged", clear=True)
        elif action == "move":
            if not target_mailbox:
                raise FastmailError("target_mailbox required for move action")
            return self.move_emails(capped, target_mailbox)
        elif action == "delete":
            return self.delete_emails(capped)
        else:
            raise FastmailError(f"Unknown action: {action}. Valid: mark_read, mark_unread, flag, unflag, move, delete")

    # -------------------------------------------------------------------
    # Masked Email
    # -------------------------------------------------------------------

    def get_masked_emails(
        self,
        state: str | None = None,
        for_domain: str | None = None,
        limit: int = 20,
    ) -> list[MaskedEmail]:
        """Get masked email addresses with optional filtering."""
        response = self._request(MaskedEmailGet(ids=None))
        masks = list(response.data) if response.data else []

        if state:
            state_enum = MaskedEmailState(state)
            masks = [m for m in masks if m.state == state_enum]
        if for_domain:
            masks = [m for m in masks if m.for_domain and for_domain.lower() in m.for_domain.lower()]

        masks.sort(key=lambda m: m.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return masks[:limit]

    def create_masked_email(
        self,
        for_domain: str,
        description: str | None = None,
        email_prefix: str | None = None,
    ) -> MaskedEmail:
        """Create a new masked email address."""
        mask = MaskedEmail(
            for_domain=for_domain,
            description=description,
            state=MaskedEmailState.ENABLED,
        )
        if email_prefix:
            mask.email_prefix = email_prefix

        response = self._request(MaskedEmailSet(create={"new": mask}))
        if response.created and "new" in response.created:
            created: MaskedEmail | None = response.created["new"]
            if created is not None:
                return created
        raise FastmailError("Failed to create masked email")

    def update_masked_email(
        self,
        mask_id: str,
        state: str | None = None,
        description: str | None = None,
        for_domain: str | None = None,
    ) -> dict[str, Any]:
        """Update a masked email address."""
        patch: dict[str, Any] = {}
        if state:
            patch["state"] = MaskedEmailState(state).value
        if description is not None:
            patch["description"] = description
        if for_domain is not None:
            patch["forDomain"] = for_domain

        if not patch:
            raise FastmailError("No fields to update")

        self._request(MaskedEmailSet(update={mask_id: patch}))
        return {"id": mask_id, **patch}

    # -------------------------------------------------------------------
    # Push (EventSource)
    # -------------------------------------------------------------------

    def check_push_status(self) -> dict[str, Any]:
        """Check EventSource availability."""
        session = self._client.jmap_session
        event_source_url = session.event_source_url if session else None
        return {
            "available": bool(event_source_url),
            "url": event_source_url or "not available",
        }

    def subscribe_push(
        self,
        types: str = "*",
        timeout: int = 60,
    ) -> list[dict[str, Any]]:
        """Subscribe to push notifications via EventSource.

        Blocks for up to ``timeout`` seconds, collecting state change events.
        Returns a list of events received.
        """
        import time

        effective_timeout = min(timeout, MAX_PUSH_TIMEOUT)

        self._client._event_source_config = EventSourceConfig(
            types=types,
            closeafter="state",
            ping=effective_timeout,
        )
        self._client._events = None  # Reset to pick up new config

        events: list[dict[str, Any]] = []
        start = time.monotonic()

        try:
            for event in self._client.events:
                elapsed = time.monotonic() - start
                if elapsed >= effective_timeout:
                    break
                event_data: dict[str, Any] = {
                    "id": event.id,
                    "changed": {},
                }
                for account_id, type_state in event.data.changed.items():
                    changes: dict[str, str] = {}
                    if type_state.email:
                        changes["Email"] = type_state.email
                    if type_state.mailbox:
                        changes["Mailbox"] = type_state.mailbox
                    if type_state.thread:
                        changes["Thread"] = type_state.thread
                    if type_state.email_delivery:
                        changes["EmailDelivery"] = type_state.email_delivery
                    if changes:
                        event_data["changed"][account_id] = changes
                events.append(event_data)
                if self._client._event_source_config.closeafter == "state":
                    break
        except Exception as e:
            logger.warning("EventSource error: %s", _scrub_token(str(e)))
            if not events:
                raise FastmailError(f"EventSource error: {_scrub_token(str(e))}") from e

        return events

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    def _get_default_identity_id(self) -> str:
        """Get the first available identity ID."""
        identities = self.get_identities()
        if not identities:
            raise FastmailError("No sender identities found")
        return identities[0].id  # type: ignore[return-value]

    def _get_mailbox_id_by_role(self, role: str) -> str:
        """Find a mailbox ID by its role (inbox, sent, drafts, trash, junk)."""
        mailboxes = self.get_mailboxes()
        for mb in mailboxes:
            if mb.role == role:
                if mb.id:
                    return mb.id
        raise NotFoundError(f"Mailbox with role '{role}' not found")

    def _get_drafts_mailbox_id(self) -> str:
        return self._get_mailbox_id_by_role("drafts")

    def _get_sent_mailbox_id(self) -> str:
        return self._get_mailbox_id_by_role("sent")

    def _get_trash_mailbox_id(self) -> str:
        return self._get_mailbox_id_by_role("trash")
