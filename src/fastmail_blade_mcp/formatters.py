"""Token-efficient output formatters for Fastmail data.

Design principles:
- Concise by default (one line per item)
- Null fields omitted
- Lists capped and annotated with total count
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastmail_blade_mcp.models import DEFAULT_LIMIT, MAX_BODY_CHARS


def format_mailbox_list(mailboxes: list[Any]) -> str:
    """Format mailbox list: name (total/unread) [role].

    Example::

        Inbox (1234/56) [inbox]
        Sent (890/0) [sent]
        Archive (4567/0)
    """
    if not mailboxes:
        return "No mailboxes found."

    lines: list[str] = []
    for mb in mailboxes:
        name = getattr(mb, "name", None) or "?"
        total = getattr(mb, "total_emails", None)
        unread = getattr(mb, "unread_emails", None)
        role = getattr(mb, "role", None)
        mb_id = getattr(mb, "id", None)

        parts = [name]
        if total is not None:
            parts.append(f"({total}/{unread or 0})")
        if role:
            parts.append(f"[{role}]")
        if mb_id:
            parts.append(f"id={mb_id}")
        lines.append(" ".join(parts))

    return "\n".join(lines)


def format_email_list(emails: list[Any], total: int | None = None, limit: int = DEFAULT_LIMIT) -> str:
    """Format email list concisely: date | sender | subject | size | flags.

    Example::

        2026-03-07 | alice@example.com | Meeting notes | 4.2 KB | $seen
        2026-03-06 | bob@example.com | Re: Project update | 1.1 KB | $seen $flagged
        … 48 more (use limit= to see more)
    """
    if not emails:
        return "No emails found."

    actual_total = total if total is not None else len(emails)
    shown = emails[:limit]
    lines: list[str] = []

    for email in shown:
        parts: list[str] = []

        # Date
        received = getattr(email, "received_at", None)
        if isinstance(received, datetime):
            parts.append(received.strftime("%Y-%m-%d %H:%M"))
        elif received:
            parts.append(str(received)[:16])
        else:
            parts.append("?")

        # Sender
        mail_from = getattr(email, "mail_from", None)
        if mail_from and len(mail_from) > 0:
            sender = mail_from[0]
            name = getattr(sender, "name", None)
            addr = getattr(sender, "email", None)
            parts.append(name or addr or "?")
        else:
            parts.append("?")

        # Subject
        subject = getattr(email, "subject", None)
        parts.append(subject or "(no subject)")

        # Size
        size = getattr(email, "size", None)
        if size:
            parts.append(_human_size(size))

        # Flags
        keywords = getattr(email, "keywords", None)
        if keywords:
            flags = " ".join(k for k in keywords if keywords[k])
            if flags:
                parts.append(flags)

        # ID
        eid = getattr(email, "id", None)
        if eid:
            parts.append(f"id={eid}")

        lines.append(" | ".join(parts))

    if actual_total > len(shown):
        lines.append(f"… {actual_total - len(shown)} more (use limit= to see more)")

    return "\n".join(lines)


def format_email_body(email: Any, html: bool = False) -> str:
    """Format a full email for reading: headers + body.

    Example::

        From: Alice <alice@example.com>
        To: Bob <bob@example.com>
        Subject: Meeting notes
        Date: 2026-03-07T10:30:00Z
        ID: Mabcdef123
        Thread: Txyz789

        Body of the email here...
    """
    lines: list[str] = []

    # Headers
    mail_from = getattr(email, "mail_from", None)
    if mail_from:
        lines.append(f"From: {_format_addresses(mail_from)}")
    to = getattr(email, "to", None)
    if to:
        lines.append(f"To: {_format_addresses(to)}")
    cc = getattr(email, "cc", None)
    if cc:
        lines.append(f"Cc: {_format_addresses(cc)}")
    bcc = getattr(email, "bcc", None)
    if bcc:
        lines.append(f"Bcc: {_format_addresses(bcc)}")
    subject = getattr(email, "subject", None)
    if subject:
        lines.append(f"Subject: {subject}")
    received = getattr(email, "received_at", None)
    if received:
        lines.append(f"Date: {received}")
    eid = getattr(email, "id", None)
    if eid:
        lines.append(f"ID: {eid}")
    thread_id = getattr(email, "thread_id", None)
    if thread_id:
        lines.append(f"Thread: {thread_id}")

    # Keywords/flags
    keywords = getattr(email, "keywords", None)
    if keywords:
        flags = [k for k in keywords if keywords[k]]
        if flags:
            lines.append(f"Flags: {' '.join(flags)}")

    # Size
    size = getattr(email, "size", None)
    if size:
        lines.append(f"Size: {_human_size(size)}")

    lines.append("")  # Blank line before body

    # Body
    body_text = _extract_body(email, html=html)
    if body_text:
        lines.append(truncate_body(body_text))
    else:
        lines.append("(no body)")

    return "\n".join(lines)


def format_thread(emails: list[Any]) -> str:
    """Format a thread as a chronological conversation.

    Example::

        [1/3] 2026-03-05 | alice@example.com | Meeting tomorrow
        Let's meet at 2pm...

        [2/3] 2026-03-05 | bob@example.com | Re: Meeting tomorrow
        Sounds good, see you then...
    """
    if not emails:
        return "Empty thread."

    parts: list[str] = []
    total = len(emails)

    for i, email in enumerate(emails, 1):
        header_parts: list[str] = [f"[{i}/{total}]"]

        received = getattr(email, "received_at", None)
        if isinstance(received, datetime):
            header_parts.append(received.strftime("%Y-%m-%d %H:%M"))
        elif received:
            header_parts.append(str(received)[:16])

        mail_from = getattr(email, "mail_from", None)
        if mail_from and len(mail_from) > 0:
            sender = mail_from[0]
            header_parts.append(getattr(sender, "name", None) or getattr(sender, "email", None) or "?")

        subject = getattr(email, "subject", None)
        if subject:
            header_parts.append(subject)

        parts.append(" | ".join(header_parts))

        body = _extract_body(email, html=False)
        if body:
            # Truncate individual thread messages more aggressively
            truncated = body[:2000]
            if len(body) > 2000:
                truncated += "\n… (truncated)"
            parts.append(truncated)
        parts.append("")  # Separator

    return "\n".join(parts).rstrip()


def format_search_snippets(
    snippets: list[Any],
    emails: list[Any],
    total: int | None = None,
    limit: int = DEFAULT_LIMIT,
) -> str:
    """Format search results with highlighted context excerpts.

    Example::

        2026-03-07 | alice@example.com | Meeting notes
          …discussed the <mark>project</mark> timeline…

        2026-03-06 | bob@example.com | Re: Budget review
          …the <mark>project</mark> budget is on track…
    """
    if not snippets:
        return "No results found."

    email_map = {getattr(e, "id", None): e for e in emails}
    actual_total = total if total is not None else len(snippets)
    shown = snippets[:limit]
    parts: list[str] = []

    for snippet in shown:
        email_id = getattr(snippet, "email_id", None)
        email = email_map.get(email_id)

        header_parts: list[str] = []
        if email:
            received = getattr(email, "received_at", None)
            if isinstance(received, datetime):
                header_parts.append(received.strftime("%Y-%m-%d"))
            mail_from = getattr(email, "mail_from", None)
            if mail_from and len(mail_from) > 0:
                sender = mail_from[0]
                header_parts.append(getattr(sender, "name", None) or getattr(sender, "email", None) or "?")
            subj = getattr(snippet, "subject", None) or getattr(email, "subject", None)
            if subj:
                header_parts.append(subj)
        else:
            header_parts.append(email_id or "?")

        parts.append(" | ".join(header_parts))

        preview = getattr(snippet, "preview", None)
        if preview:
            parts.append(f"  {preview}")
        parts.append("")

    if actual_total > len(shown):
        parts.append(f"… {actual_total - len(shown)} more results")

    return "\n".join(parts).rstrip()


def format_masked_email_list(masks: list[Any], total: int | None = None, limit: int = DEFAULT_LIMIT) -> str:
    """Format masked email list.

    Example::

        abc123@fastmail.com | enabled | example.com | "My service" | last: 2026-03-01
        def456@fastmail.com | disabled | other.com | "Old account"
    """
    if not masks:
        return "No masked emails found."

    actual_total = total if total is not None else len(masks)
    shown = masks[:limit]
    lines: list[str] = []

    for mask in shown:
        parts: list[str] = []
        email = getattr(mask, "email", None)
        parts.append(email or "?")

        state = getattr(mask, "state", None)
        if state:
            parts.append(state.value if hasattr(state, "value") else str(state))

        domain = getattr(mask, "for_domain", None)
        if domain:
            parts.append(domain)

        desc = getattr(mask, "description", None)
        if desc:
            parts.append(f'"{desc}"')

        last_msg = getattr(mask, "last_message_at", None)
        if last_msg:
            if isinstance(last_msg, datetime):
                parts.append(f"last: {last_msg.strftime('%Y-%m-%d')}")
            else:
                parts.append(f"last: {str(last_msg)[:10]}")

        mask_id = getattr(mask, "id", None)
        if mask_id:
            parts.append(f"id={mask_id}")

        lines.append(" | ".join(parts))

    if actual_total > len(shown):
        lines.append(f"… {actual_total - len(shown)} more (use limit= to see more)")

    return "\n".join(lines)


def format_session_info(info: dict[str, Any]) -> str:
    """Format JMAP session info.

    Example::

        Account: user@fastmail.com
        Account ID: abc123
        Capabilities: urn:ietf:params:jmap:core, urn:ietf:params:jmap:mail
    """
    lines: list[str] = []
    if email := info.get("email"):
        lines.append(f"Account: {email}")
    if account_id := info.get("account_id"):
        lines.append(f"Account ID: {account_id}")
    if caps := info.get("capabilities"):
        lines.append(f"Capabilities: {', '.join(caps)}")
    if acaps := info.get("account_capabilities"):
        lines.append(f"Account capabilities: {', '.join(acaps)}")
    return "\n".join(lines) if lines else str(info)


def format_identity_list(identities: list[Any]) -> str:
    """Format sender identity list.

    Example::

        Piers <piers@fastmail.com> id=abc123
        Work <piers@work.com> id=def456
    """
    if not identities:
        return "No identities found."

    lines: list[str] = []
    for ident in identities:
        name = getattr(ident, "name", None)
        email = getattr(ident, "email", None)
        ident_id = getattr(ident, "id", None)

        if name and email:
            line = f"{name} <{email}>"
        elif email:
            line = email
        else:
            line = "?"

        if ident_id:
            line += f" id={ident_id}"
        lines.append(line)

    return "\n".join(lines)


def format_changes(changes: dict[str, Any]) -> str:
    """Format email changes response.

    Example::

        State: s123 → s456
        Has more: false
        Created (3): M001, M002, M003
        Updated (1): M004
        Destroyed (0):
    """
    created = changes.get("created", [])
    updated = changes.get("updated", [])
    destroyed = changes.get("destroyed", [])

    def _id_list(ids: list[str], cap: int = 20) -> str:
        if not ids:
            return ""
        shown = ids[:cap]
        result = ", ".join(shown)
        if len(ids) > cap:
            result += f" … +{len(ids) - cap} more"
        return result

    lines = [
        f"State: {changes.get('old_state', '?')} → {changes.get('new_state', '?')}",
        f"Has more: {str(changes.get('has_more_changes', False)).lower()}",
        f"Created ({len(created)}): {_id_list(created)}",
        f"Updated ({len(updated)}): {_id_list(updated)}",
        f"Destroyed ({len(destroyed)}): {_id_list(destroyed)}",
    ]
    return "\n".join(lines)


def format_push_events(events: list[dict[str, Any]]) -> str:
    """Format push notification events."""
    if not events:
        return "No events received within timeout."

    lines: list[str] = []
    for event in events:
        event_id = event.get("id", "?")
        changed = event.get("changed", {})
        for account_id, changes in changed.items():
            change_parts = [f"{k}: {v}" for k, v in changes.items()]
            lines.append(f"Event {event_id}: {', '.join(change_parts)}")

    return "\n".join(lines) if lines else "Events received but no state changes."


def format_push_status(status: dict[str, Any]) -> str:
    """Format push status info."""
    available = status.get("available", False)
    lines = [f"EventSource: {'available' if available else 'not available'}"]
    if url := status.get("url"):
        lines.append(f"URL: {url}")
    return "\n".join(lines)


def truncate_body(text: str, max_chars: int = MAX_BODY_CHARS) -> str:
    """Truncate long body text with annotation."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n… (truncated, {len(text) - max_chars} more characters)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_addresses(addrs: list[Any]) -> str:
    """Format a list of email addresses."""
    parts = []
    for addr in addrs:
        name = getattr(addr, "name", None)
        email = getattr(addr, "email", None)
        if name and email:
            parts.append(f"{name} <{email}>")
        elif email:
            parts.append(email)
        elif name:
            parts.append(name)
    return ", ".join(parts)


def _extract_body(email: Any, html: bool = False) -> str:
    """Extract body text from an email object."""
    body_values = getattr(email, "body_values", None)
    if not body_values:
        preview = getattr(email, "preview", None)
        return preview or ""

    if html:
        html_body = getattr(email, "html_body", None)
        if html_body:
            for part in html_body:
                part_id = getattr(part, "part_id", None)
                if part_id and part_id in body_values:
                    bv = body_values[part_id]
                    value = getattr(bv, "value", None)
                    if value:
                        return str(value)

    text_body = getattr(email, "text_body", None)
    if text_body:
        for part in text_body:
            part_id = getattr(part, "part_id", None)
            if part_id and part_id in body_values:
                bv = body_values[part_id]
                value = getattr(bv, "value", None)
                if value:
                    return str(value)

    # Fallback: try any body value
    for bv in body_values.values():
        value = getattr(bv, "value", None)
        if value:
            return str(value)

    return ""


def _human_size(size_bytes: int | float) -> str:
    """Convert bytes to human-readable size."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{int(size_bytes)} B"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
