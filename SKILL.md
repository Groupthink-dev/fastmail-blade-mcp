---
name: fastmail-blade
description: Fastmail email operations via JMAP — read, search, send, masked email, push
version: 0.1.0
permissions:
  read:
    - fastmail_info
    - fastmail_identities
    - mail_mailboxes
    - mail_read
    - mail_search
    - mail_threads
    - mail_snippets
    - mail_state
    - mail_changes
    - masked_list
    - push_subscribe
    - push_status
  write:
    - mail_send
    - mail_reply
    - mail_move
    - mail_flag
    - mail_delete
    - mail_bulk
    - masked_create
    - masked_update
---

# Fastmail Blade MCP — Skill Guide

## Token Efficiency Rules (MANDATORY)

1. **Use `limit=` on search/list tools** — default is 20, reduce for browsing
2. **Use `mail_search` before `mail_read`** — find emails first, then read specific ones
3. **Use `mail_mailboxes` to get IDs** — mailbox IDs are required for `in_mailbox` filters
4. **Use `mail_threads` for conversations** — more efficient than reading individual emails
5. **Use `mail_snippets` for content search** — shows matching context without full bodies
6. **Use `fastmail_identities` before sending** — get identity IDs for `from_identity`
7. **Use `push_status` before `push_subscribe`** — confirm EventSource availability first
8. **Never read all emails** — always filter by date, sender, mailbox, or keywords

## Quick Start — 5 Most Common Operations

```
mail_search limit=10                          → Recent emails
mail_read id="M001"                           → Read specific email
mail_search from_addr="alice@example.com"     → Find emails from sender
masked_list state="enabled" limit=10          → Active masked aliases
fastmail_info                                 → Health check
```

## Tool Reference

### Meta
- **fastmail_info** — Account email, capabilities, limits. Health check.
- **fastmail_identities** — Sender identities (ID, name, email). Need ID for sending.

### Email Read
- **mail_mailboxes** — All mailboxes with ID, name, total/unread, role.
- **mail_read** — Full email: headers + body. Use `id=` from search results.
- **mail_search** — Search with filters. Returns date, sender, subject, size, flags.
- **mail_threads** — Chronological conversation view. Use `id=` (thread ID) from search.
- **mail_snippets** — Search with highlighted context excerpts. Best for content search.

### Email State & Changes
- **mail_state** — Current JMAP Email state string. Use to initialise change tracking.
- **mail_changes** — Incremental changes since a state. Returns created/updated/destroyed IDs. Falls back to error if state is >30 days old.

### Email Write (requires FASTMAIL_WRITE_ENABLED=true)
- **mail_send** — Send new email. Comma-separated recipients. Plain text body.
- **mail_reply** — Reply to email. Preserves threading. `reply_all=true` for all recipients.
- **mail_move** — Move emails to mailbox. Use mailbox IDs from `mail_mailboxes`.
- **mail_flag** — Set/clear keywords. Common: `$flagged`, `$seen`, `$answered`.

### Email Manage (requires FASTMAIL_WRITE_ENABLED=true)
- **mail_delete** — Move to Trash (default) or permanently destroy.
- **mail_bulk** — Bulk action on up to 50 emails. Actions: mark_read, mark_unread, flag, unflag, move, delete.

### Masked Email
- **masked_list** — List masked aliases with state, domain, description. Filter by state/domain.
- **masked_create** — Create new alias for a domain. Requires write enabled.
- **masked_update** — Change state (enabled/disabled/deleted) or description. Requires write enabled.

### Push Notifications
- **push_subscribe** — Listen for state changes via EventSource. Bounded timeout (default 60s, max 300s).
- **push_status** — Check EventSource availability.

## Workflow Examples

### Email Triage
```
1. mail_mailboxes                             → Get Inbox mailbox ID
2. mail_search in_mailbox="mb-inbox" limit=20 → Recent inbox emails
3. mail_read id="M001"                        → Read specific email
4. mail_threads id="T001"                     → Get full conversation
5. mail_flag ids="M001" keyword="$seen"       → Mark as read
```

### Find and Reply
```
1. mail_search from_addr="alice@example.com" limit=5  → Find emails from Alice
2. mail_read id="M001"                                → Read the email
3. fastmail_identities                                 → Get sender identity
4. mail_reply id="M001" body="Thanks!" from_identity="id-primary"
```

### Masked Email Management
```
1. masked_list state="enabled" limit=20       → Active aliases
2. masked_list for_domain="netflix"           → Find Netflix alias
3. masked_create for_domain="newsite.com" description="New service"
4. masked_update id="me-001" state="disabled" → Disable old alias
```

### Incremental Sync (State Watermark)
```
1. mail_state                                → Get current state string
   (persist state for next run)
2. mail_changes since_state="s123"           → Get created/updated/destroyed IDs
3. mail_read id="M001"                       → Read new emails by ID
   (if "State too old" error, fall back to mail_search with after= filter)
```

### Monitor for New Mail
```
1. push_status                                → Check availability
2. push_subscribe timeout=60                  → Wait for changes
3. mail_search after="2026-03-08" limit=5     → Fetch new emails
```

## Common Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `id` | Email or thread ID | `id="M001"` |
| `ids` | Comma-separated IDs | `ids="M001,M002,M003"` |
| `from_addr` | Sender email filter | `from_addr="alice@example.com"` |
| `to_addr` | Recipient filter | `to_addr="bob@example.com"` |
| `subject` | Subject text filter | `subject="Meeting"` |
| `body` | Body text filter | `body="project update"` |
| `after` | Date filter (ISO 8601) | `after="2026-03-01"` |
| `before` | Date filter (ISO 8601) | `before="2026-03-08"` |
| `in_mailbox` | Mailbox ID filter | `in_mailbox="mb-inbox"` |
| `has_keyword` | Must have keyword | `has_keyword="$flagged"` |
| `not_keyword` | Must not have keyword | `not_keyword="$seen"` |
| `limit` | Max results (default: 20) | `limit=10` |
| `since_state` | JMAP state for changes | `since_state="s123"` |
| `max_changes` | Max changes (default: 100) | `max_changes=50` |
| `state` | Masked email state | `state="enabled"` |
| `for_domain` | Masked email domain | `for_domain="netflix.com"` |

## Security Notes

- Write operations blocked unless `FASTMAIL_WRITE_ENABLED=true`
- `mail_bulk` capped at 50 emails per operation
- `push_subscribe` bounded at 300s max timeout
- API token never appears in tool output
- `mail_delete` defaults to Trash (not permanent)
