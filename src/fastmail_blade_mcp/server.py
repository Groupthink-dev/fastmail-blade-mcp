"""Fastmail Blade MCP Server — email, masked email, and push notifications.

Wraps the Fastmail JMAP API via ``jmapc`` as MCP tools. Token-efficient by default:
concise output, capped lists, null-field omission.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from fastmail_blade_mcp.client import FastmailClient, FastmailError
from fastmail_blade_mcp.formatters import (
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
)
from fastmail_blade_mcp.models import DEFAULT_LIMIT, MAX_BATCH_SIZE, require_write

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transport configuration
# ---------------------------------------------------------------------------

TRANSPORT = os.environ.get("FASTMAIL_MCP_TRANSPORT", "stdio")
HTTP_HOST = os.environ.get("FASTMAIL_MCP_HOST", "127.0.0.1")
HTTP_PORT = int(os.environ.get("FASTMAIL_MCP_PORT", "8767"))

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "FastmailBlade",
    instructions=(
        "Fastmail email operations via JMAP. Read, search, send, and manage email. "
        "Masked email aliases for privacy. Push notifications via EventSource. "
        "Write operations require FASTMAIL_WRITE_ENABLED=true."
    ),
)

# Lazy-initialized client
_client: FastmailClient | None = None


def _get_client() -> FastmailClient:
    """Get or create the FastmailClient singleton."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = FastmailClient()
        logger.info("FastmailClient: account=%s", _client.account_id)
    return _client


def _error_response(e: FastmailError) -> str:
    """Format a client error as a user-friendly string."""
    return f"Error: {e}"


async def _run(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a blocking client method in a thread to avoid blocking the event loop."""
    return await asyncio.to_thread(fn, *args, **kwargs)


# ===========================================================================
# META TOOLS
# ===========================================================================


@mcp.tool
async def fastmail_info() -> str:
    """Get Fastmail account info: email, capabilities, limits.

    Use this as a health check and to confirm account connectivity.
    """
    try:
        result = await _run(_get_client().get_session_info)
        return format_session_info(result)
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in fastmail_info")
        return f"Error: {e}"


@mcp.tool
async def fastmail_identities() -> str:
    """Get sender identities (ID, name, email).

    Use to find identity IDs for ``mail_send`` and ``mail_reply``.
    """
    try:
        result = await _run(_get_client().get_identities)
        return format_identity_list(result)
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in fastmail_identities")
        return f"Error: {e}"


# ===========================================================================
# EMAIL READ TOOLS
# ===========================================================================


@mcp.tool
async def mail_mailboxes() -> str:
    """List all mailboxes with ID, name, total/unread counts, and role.

    Returns Inbox, Sent, Drafts, Trash, and any custom folders.
    """
    try:
        result = await _run(_get_client().get_mailboxes)
        return format_mailbox_list(result)
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in mail_mailboxes")
        return f"Error: {e}"


@mcp.tool
async def mail_read(
    id: Annotated[str, Field(description="Email ID to read")],
    html: Annotated[bool, Field(description="Include HTML body (default: text only)")] = False,
) -> str:
    """Read a full email: headers + body.

    Returns From, To, Cc, Subject, Date, flags, and body text.
    Use ``html=true`` to also fetch the HTML body.
    """
    try:
        email = await _run(_get_client().get_email, id, html=html)
        return format_email_body(email, html=html)
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in mail_read")
        return f"Error: {e}"


@mcp.tool
async def mail_search(
    from_addr: Annotated[str | None, Field(description="Filter by sender email address")] = None,
    to_addr: Annotated[str | None, Field(description="Filter by recipient email address")] = None,
    subject: Annotated[str | None, Field(description="Filter by subject text")] = None,
    body: Annotated[str | None, Field(description="Filter by body text")] = None,
    after: Annotated[str | None, Field(description="Emails after this date (ISO 8601, e.g. '2026-03-01')")] = None,
    before: Annotated[str | None, Field(description="Emails before this date (ISO 8601)")] = None,
    in_mailbox: Annotated[str | None, Field(description="Mailbox ID to search within")] = None,
    has_keyword: Annotated[str | None, Field(description="Must have keyword (e.g. '$flagged', '$seen')")] = None,
    not_keyword: Annotated[str | None, Field(description="Must not have keyword")] = None,
    limit: Annotated[int, Field(description="Max results (default: 20)")] = DEFAULT_LIMIT,
) -> str:
    """Search emails with filters. Returns concise list: date, sender, subject, size, flags.

    Use ``in_mailbox`` with a mailbox ID from ``mail_mailboxes``.
    At least one filter should be provided.
    """
    try:
        emails, total = await _run(
            _get_client().search_emails,
            from_addr=from_addr,
            to_addr=to_addr,
            subject=subject,
            body=body,
            after=after,
            before=before,
            in_mailbox=in_mailbox,
            has_keyword=has_keyword,
            not_keyword=not_keyword,
            limit=limit,
        )
        return format_email_list(emails, total=total, limit=limit)
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in mail_search")
        return f"Error: {e}"


@mcp.tool
async def mail_threads(
    id: Annotated[str, Field(description="Thread ID to retrieve")],
) -> str:
    """Get all messages in a thread, ordered chronologically.

    Returns a conversation view with sender, subject, and body excerpt per message.
    Thread IDs are returned by ``mail_search`` and ``mail_read``.
    """
    try:
        emails = await _run(_get_client().get_thread, id)
        return format_thread(emails)
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in mail_threads")
        return f"Error: {e}"


@mcp.tool
async def mail_snippets(
    from_addr: Annotated[str | None, Field(description="Filter by sender email address")] = None,
    subject: Annotated[str | None, Field(description="Filter by subject text")] = None,
    body: Annotated[str | None, Field(description="Filter by body text")] = None,
    after: Annotated[str | None, Field(description="Emails after this date (ISO 8601)")] = None,
    before: Annotated[str | None, Field(description="Emails before this date (ISO 8601)")] = None,
    in_mailbox: Annotated[str | None, Field(description="Mailbox ID to search within")] = None,
    limit: Annotated[int, Field(description="Max results (default: 20)")] = DEFAULT_LIMIT,
) -> str:
    """Search emails with highlighted context excerpts.

    Like ``mail_search`` but includes matching text snippets around search terms.
    Best for finding specific content within emails.
    """
    try:
        snippets, emails, total = await _run(
            _get_client().get_snippets,
            from_addr=from_addr,
            subject=subject,
            body=body,
            after=after,
            before=before,
            in_mailbox=in_mailbox,
            limit=limit,
        )
        return format_search_snippets(snippets, emails, total=total, limit=limit)
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in mail_snippets")
        return f"Error: {e}"


# ===========================================================================
# EMAIL WRITE TOOLS (gated: FASTMAIL_WRITE_ENABLED=true)
# ===========================================================================


@mcp.tool
async def mail_send(
    to: Annotated[str, Field(description="Recipient email(s), comma-separated")],
    subject: Annotated[str, Field(description="Email subject")],
    body: Annotated[str, Field(description="Email body (plain text)")],
    from_identity: Annotated[str | None, Field(description="Sender identity ID (from fastmail_identities)")] = None,
    cc: Annotated[str | None, Field(description="CC recipient(s), comma-separated")] = None,
    bcc: Annotated[str | None, Field(description="BCC recipient(s), comma-separated")] = None,
) -> str:
    """Send a new email. Requires FASTMAIL_WRITE_ENABLED=true.

    Use ``fastmail_identities`` to find available sender identity IDs.
    """
    if err := require_write():
        return err
    try:
        to_list = [addr.strip() for addr in to.split(",") if addr.strip()]
        cc_list = [addr.strip() for addr in cc.split(",") if addr.strip()] if cc else None
        bcc_list = [addr.strip() for addr in bcc.split(",") if addr.strip()] if bcc else None
        logger.info("mail_send: to=%s, subject=%s", to_list, subject[:50])
        submission_id = await _run(
            _get_client().send_email,
            to=to_list,
            subject=subject,
            body=body,
            from_identity=from_identity,
            cc=cc_list,
            bcc=bcc_list,
        )
        return f"Sent. Submission ID: {submission_id}"
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in mail_send")
        return f"Error: {e}"


@mcp.tool
async def mail_reply(
    id: Annotated[str, Field(description="Email ID to reply to")],
    body: Annotated[str, Field(description="Reply body (plain text)")],
    reply_all: Annotated[bool, Field(description="Reply to all recipients (default: false)")] = False,
    from_identity: Annotated[str | None, Field(description="Sender identity ID")] = None,
) -> str:
    """Reply to an email. Preserves threading. Requires FASTMAIL_WRITE_ENABLED=true.

    Uses ``reply_all=true`` to reply to all original recipients.
    """
    if err := require_write():
        return err
    try:
        logger.info("mail_reply: id=%s, reply_all=%s", id, reply_all)
        submission_id = await _run(
            _get_client().reply_to_email,
            email_id=id,
            body=body,
            reply_all=reply_all,
            from_identity=from_identity,
        )
        return f"Reply sent. Submission ID: {submission_id}"
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in mail_reply")
        return f"Error: {e}"


@mcp.tool
async def mail_move(
    ids: Annotated[str, Field(description="Email ID(s), comma-separated")],
    to_mailbox: Annotated[str, Field(description="Destination mailbox ID")],
    from_mailbox: Annotated[str | None, Field(description="Source mailbox ID (optional, improves accuracy)")] = None,
) -> str:
    """Move emails to a mailbox. Requires FASTMAIL_WRITE_ENABLED=true.

    Use ``mail_mailboxes`` to find mailbox IDs.
    """
    if err := require_write():
        return err
    try:
        id_list = [eid.strip() for eid in ids.split(",") if eid.strip()]
        logger.info("mail_move: %d emails to %s", len(id_list), to_mailbox)
        count = await _run(_get_client().move_emails, id_list, to_mailbox, from_mailbox)
        return f"Moved {count} email(s)."
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in mail_move")
        return f"Error: {e}"


@mcp.tool
async def mail_flag(
    ids: Annotated[str, Field(description="Email ID(s), comma-separated")],
    keyword: Annotated[str, Field(description="Keyword to set (default: '$flagged')")] = "$flagged",
    clear: Annotated[bool, Field(description="Remove the keyword instead of setting it")] = False,
) -> str:
    """Flag or unflag emails. Requires FASTMAIL_WRITE_ENABLED=true.

    Common keywords: ``$flagged``, ``$seen``, ``$answered``, ``$draft``.
    """
    if err := require_write():
        return err
    try:
        id_list = [eid.strip() for eid in ids.split(",") if eid.strip()]
        action = "Cleared" if clear else "Set"
        logger.info("mail_flag: %s %s on %d emails", action.lower(), keyword, len(id_list))
        count = await _run(_get_client().flag_emails, id_list, keyword, clear)
        return f"{action} '{keyword}' on {count} email(s)."
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in mail_flag")
        return f"Error: {e}"


# ===========================================================================
# EMAIL MANAGE TOOLS (gated)
# ===========================================================================


@mcp.tool
async def mail_delete(
    ids: Annotated[str, Field(description="Email ID(s), comma-separated")],
    permanent: Annotated[bool, Field(description="Permanently delete (default: move to Trash)")] = False,
) -> str:
    """Delete emails. Moves to Trash by default. Requires FASTMAIL_WRITE_ENABLED=true.

    Use ``permanent=true`` to permanently destroy — cannot be undone.
    """
    if err := require_write():
        return err
    try:
        id_list = [eid.strip() for eid in ids.split(",") if eid.strip()]
        action = "Permanently deleted" if permanent else "Moved to Trash"
        logger.info("mail_delete: %d emails, permanent=%s", len(id_list), permanent)
        count = await _run(_get_client().delete_emails, id_list, permanent)
        return f"{action}: {count} email(s)."
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in mail_delete")
        return f"Error: {e}"


@mcp.tool
async def mail_bulk(
    ids: Annotated[str, Field(description="Email ID(s), comma-separated (max 50)")],
    action: Annotated[
        str,
        Field(description="Action: mark_read, mark_unread, flag, unflag, move, delete"),
    ],
    target_mailbox: Annotated[str | None, Field(description="Target mailbox ID (required for 'move')")] = None,
) -> str:
    """Bulk action on emails. Capped at 50. Requires FASTMAIL_WRITE_ENABLED=true.

    Actions: ``mark_read``, ``mark_unread``, ``flag``, ``unflag``, ``move``, ``delete``.
    """
    if err := require_write():
        return err
    try:
        id_list = [eid.strip() for eid in ids.split(",") if eid.strip()]
        if len(id_list) > MAX_BATCH_SIZE:
            return f"Error: Maximum {MAX_BATCH_SIZE} emails per bulk operation. Got {len(id_list)}."
        logger.info("mail_bulk: %s on %d emails", action, len(id_list))
        count = await _run(_get_client().bulk_action, id_list, action, target_mailbox)
        return f"Bulk {action}: {count} email(s) affected."
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in mail_bulk")
        return f"Error: {e}"


# ===========================================================================
# MASKED EMAIL TOOLS
# ===========================================================================


@mcp.tool
async def masked_list(
    state: Annotated[str | None, Field(description="Filter by state: pending, enabled, disabled, deleted")] = None,
    for_domain: Annotated[str | None, Field(description="Filter by domain (partial match)")] = None,
    limit: Annotated[int, Field(description="Max results (default: 20)")] = DEFAULT_LIMIT,
) -> str:
    """List masked email addresses with state, domain, description, and last message date.

    Masked emails are privacy aliases that forward to your real inbox.
    """
    try:
        masks = await _run(_get_client().get_masked_emails, state=state, for_domain=for_domain, limit=limit)
        return format_masked_email_list(masks, limit=limit)
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in masked_list")
        return f"Error: {e}"


@mcp.tool
async def masked_create(
    for_domain: Annotated[str, Field(description="Domain this alias is for (e.g. 'netflix.com')")],
    description: Annotated[str | None, Field(description="Description (e.g. 'Netflix account')")] = None,
    email_prefix: Annotated[str | None, Field(description="Preferred email prefix (may be adjusted)")] = None,
) -> str:
    """Create a new masked email alias. Requires FASTMAIL_WRITE_ENABLED=true.

    Returns the new masked email address and ID.
    """
    if err := require_write():
        return err
    try:
        logger.info("masked_create: domain=%s", for_domain)
        mask = await _run(_get_client().create_masked_email, for_domain, description, email_prefix)
        email = getattr(mask, "email", "?")
        mask_id = getattr(mask, "id", "?")
        return f"Created: {email} (id={mask_id})"
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in masked_create")
        return f"Error: {e}"


@mcp.tool
async def masked_update(
    id: Annotated[str, Field(description="Masked email ID to update")],
    state: Annotated[str | None, Field(description="New state: enabled, disabled, deleted")] = None,
    description: Annotated[str | None, Field(description="New description")] = None,
    for_domain: Annotated[str | None, Field(description="New domain")] = None,
) -> str:
    """Update a masked email alias. Requires FASTMAIL_WRITE_ENABLED=true.

    Use ``state=disabled`` to stop forwarding, ``state=deleted`` to remove.
    """
    if err := require_write():
        return err
    try:
        logger.info("masked_update: id=%s", id)
        result = await _run(_get_client().update_masked_email, id, state, description, for_domain)
        return f"Updated: {result}"
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in masked_update")
        return f"Error: {e}"


# ===========================================================================
# PUSH NOTIFICATION TOOLS
# ===========================================================================


@mcp.tool
async def push_subscribe(
    types: Annotated[str, Field(description="Event types to listen for (default: '*' for all)")] = "*",
    timeout: Annotated[int, Field(description="Max wait time in seconds (default: 60, max: 300)")] = 60,
) -> str:
    """Subscribe to push notifications via EventSource. Blocks until events arrive or timeout.

    Returns state change events (Email, Mailbox, Thread changes).
    Use ``push_status`` to check availability first.
    """
    try:
        events = await _run(_get_client().subscribe_push, types=types, timeout=timeout)
        return format_push_events(events)
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in push_subscribe")
        return f"Error: {e}"


@mcp.tool
async def push_status() -> str:
    """Check EventSource push notification availability and connection status.

    Reports whether the JMAP server supports EventSource and the endpoint URL.
    """
    try:
        result = await _run(_get_client().check_push_status)
        return format_push_status(result)
    except FastmailError as e:
        return _error_response(e)
    except Exception as e:
        logger.exception("Unexpected error in push_status")
        return f"Error: {e}"


# ===========================================================================
# Entry point
# ===========================================================================


def main() -> None:
    """Main entry point for the Fastmail Blade MCP server."""
    if TRANSPORT == "http":
        from starlette.middleware import Middleware

        from fastmail_blade_mcp.auth import BearerAuthMiddleware, get_bearer_token

        bearer = get_bearer_token()
        logger.info("Starting HTTP transport on %s:%s", HTTP_HOST, HTTP_PORT)
        if bearer:
            logger.info("Bearer token auth enabled (FASTMAIL_MCP_API_TOKEN is set)")
        else:
            logger.info("Bearer token auth disabled (no FASTMAIL_MCP_API_TOKEN)")
        mcp.run(
            transport="http",
            host=HTTP_HOST,
            port=HTTP_PORT,
            middleware=[Middleware(BearerAuthMiddleware)],
        )
    else:
        mcp.run()
