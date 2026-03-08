# Fastmail Blade MCP

Fastmail JMAP MCP Server — email, masked email, and push notifications. Each MCP tool is a "blade" — the sharpest instrument for its mail operation.

Wraps the [Fastmail JMAP API](https://www.fastmail.com/dev/) via [jmapc](https://github.com/smkent/jmapc) as an MCP server using [FastMCP 2.0](https://github.com/jlowin/fastmcp).

## Features

- **18 tools**: email read/write/manage, masked email, push notifications, meta
- **Masked Email management** — no other MCP server exposes this Fastmail extension
- **JMAP Push (EventSource)** — real-time state change notifications
- **Write-gate** — all write operations disabled by default (`FASTMAIL_WRITE_ENABLED=true`)
- **Token-efficient** — concise output, capped lists, null-field omission
- **Batch limits** — `mail_bulk` capped at 50, `mail_search` defaults to 20
- **SKILL.md** — self-teaching instructions for Claude

## Requirements

- macOS (tested) or Linux
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Fastmail account with API token

## Quick Start

```bash
# Clone and install
cd fastmail-blade-mcp
uv sync

# Set your API token
export FASTMAIL_API_TOKEN=fmu1-xxxxxxxx

# Run (stdio transport)
uv run fastmail-blade-mcp
```

### Claude Code

```bash
claude mcp add fastmail-blade -- uv run --directory ~/src/fastmail-blade-mcp fastmail-blade-mcp
```

### Claude Desktop (claude_desktop_config.json)

```json
{
  "mcpServers": {
    "fastmail-blade": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/fastmail-blade-mcp", "fastmail-blade-mcp"],
      "env": {
        "FASTMAIL_API_TOKEN": "fmu1-xxxxxxxx",
        "FASTMAIL_WRITE_ENABLED": "false"
      }
    }
  }
}
```

## Tools (18)

### Email Read (5)

| Tool | Description |
|------|-------------|
| `mail_mailboxes` | Mailbox list with ID, name, total/unread, role |
| `mail_read` | Full email: headers + body |
| `mail_search` | Search with filters (sender, subject, date, mailbox, keywords) |
| `mail_threads` | Chronological conversation view |
| `mail_snippets` | Search with highlighted context excerpts |

### Email Write (4, gated)

| Tool | Description |
|------|-------------|
| `mail_send` | Send new email |
| `mail_reply` | Reply (preserves threading) |
| `mail_move` | Move to mailbox |
| `mail_flag` | Set/clear keywords ($flagged, $seen, etc.) |

### Email Manage (2, gated)

| Tool | Description |
|------|-------------|
| `mail_delete` | Move to Trash (default) or permanently destroy |
| `mail_bulk` | Bulk action on up to 50 emails |

### Masked Email (3)

| Tool | Description |
|------|-------------|
| `masked_list` | List aliases with state, domain, description |
| `masked_create` | Create new masked alias (gated) |
| `masked_update` | Update state/description (gated) |

### Push (2)

| Tool | Description |
|------|-------------|
| `push_subscribe` | Listen for state changes via EventSource |
| `push_status` | Check EventSource availability |

### Meta (2)

| Tool | Description |
|------|-------------|
| `fastmail_info` | Account info, capabilities (health check) |
| `fastmail_identities` | Sender identities (ID, name, email) |

## Security

| Layer | Control |
|-------|---------|
| Secrets | `FASTMAIL_API_TOKEN` from env (never logged) |
| Transport | stdio default (no network exposure) |
| Write gate | `FASTMAIL_WRITE_ENABLED` default false |
| Batch limits | `mail_bulk` capped at 50 |
| Token scrubbing | API token removed from all error output |
| HTTP auth | Optional bearer token middleware |

## HTTP Transport

```bash
export FASTMAIL_MCP_TRANSPORT=http
export FASTMAIL_MCP_HOST=127.0.0.1
export FASTMAIL_MCP_PORT=8767
export FASTMAIL_MCP_API_TOKEN=your-secret-token

uv run fastmail-blade-mcp
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FASTMAIL_API_TOKEN` | (required) | Fastmail API token |
| `FASTMAIL_WRITE_ENABLED` | `false` | Enable write operations |
| `FASTMAIL_MCP_TRANSPORT` | `stdio` | Transport: `stdio` or `http` |
| `FASTMAIL_MCP_HOST` | `127.0.0.1` | HTTP bind host |
| `FASTMAIL_MCP_PORT` | `8767` | HTTP bind port |
| `FASTMAIL_MCP_API_TOKEN` | (none) | Bearer token for HTTP auth |

## Development

```bash
make install-dev    # Install with dev dependencies
make test           # Run unit tests (92 tests, mocked)
make test-e2e       # Run E2E tests (requires live Fastmail)
make check          # Lint + format + type-check
make run            # Start the server
```

## License

MIT
