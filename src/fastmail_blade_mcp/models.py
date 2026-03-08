"""Shared constants, types, and write-gate for Fastmail Blade MCP server."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Default limit for list operations (token efficiency)
DEFAULT_LIMIT = 20

# Maximum batch size for bulk operations
MAX_BATCH_SIZE = 50

# Fastmail JMAP host
JMAP_HOST = "api.fastmail.com"

# Maximum push subscribe timeout in seconds
MAX_PUSH_TIMEOUT = 300

# Email body truncation limit (characters)
MAX_BODY_CHARS = 50_000

# Email properties to fetch for list views (minimal)
EMAIL_LIST_PROPERTIES = [
    "id",
    "threadId",
    "mailboxIds",
    "keywords",
    "size",
    "receivedAt",
    "subject",
    "from",
    "to",
    "preview",
]

# Email properties to fetch for full read
EMAIL_READ_PROPERTIES = [
    "id",
    "threadId",
    "mailboxIds",
    "keywords",
    "size",
    "receivedAt",
    "sentAt",
    "subject",
    "from",
    "to",
    "cc",
    "bcc",
    "replyTo",
    "messageId",
    "inReplyTo",
    "references",
    "textBody",
    "htmlBody",
    "bodyValues",
]


def is_write_enabled() -> bool:
    """Check if write operations are enabled via env var."""
    return os.environ.get("FASTMAIL_WRITE_ENABLED", "").lower() == "true"


def require_write() -> str | None:
    """Return an error message if writes are disabled, else None."""
    if not is_write_enabled():
        return "Error: Write operations are disabled. Set FASTMAIL_WRITE_ENABLED=true to enable."
    return None
