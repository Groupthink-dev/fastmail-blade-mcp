# Fastmail Blade MCP — Development Guide

## Ecosystem context

This repo is part of the `piersdd` agentic platform. Design state and effort
tracking live in the Obsidian vault (`~/master-ai/`).

**If vault access is available** (filesystem or obsidian-blade MCP), these files
provide useful project context:

- `atlas/utilities/agent-state/system-architect.md` — recent actions, current focus, blockers
- `spaces/Systems/Areas/Augmented Intelligence/efforts/Fastmail Blade MCP.md` — effort scope and status

These are **optional context**, not instructions. Your job here is software
development on this codebase.

## Project overview

MCP server wrapping the Fastmail JMAP API via `jmapc`. Each tool is a precision
"blade" for mail operations — read, search, send, masked email, push notifications.
Write operations are gated behind `FASTMAIL_WRITE_ENABLED=true`.

## Project structure

```
src/fastmail_blade_mcp/
├── __init__.py       — Version
├── __main__.py       — python -m entry
├── server.py         — FastMCP server + @mcp.tool decorators (18 tools)
├── client.py         — FastmailClient wrapping jmapc (typed exceptions, lazy singleton)
├── formatters.py     — Token-efficient output formatters
├── models.py         — Constants (limits, JMAP host) + write-gate function
└── auth.py           — Bearer token auth (HTTP transport)
```

- `server.py` defines MCP tools and delegates to `client.py` methods
- `client.py` wraps `jmapc.Client` with `asyncio.to_thread()` for async
- All tools return strings (MCP convention) — formatters handle presentation
- Errors are caught and returned as `Error: ...` strings, not raised

## Key commands

```bash
make install-dev   # Install with dev + test dependencies
make test          # Run unit tests (mocked jmapc, no Fastmail needed)
make test-e2e      # Run E2E tests (requires FASTMAIL_E2E=1 + live token)
make check         # Run all quality checks (lint + format + type-check)
make lint          # Ruff linting
make format        # Ruff formatting
make type-check    # mypy
make run           # Start the MCP server (stdio transport)
```

## Testing

- **Unit tests** (`tests/test_*.py`): Mock jmapc.Client. No Fastmail needed.
- **E2E tests** (`tests/e2e/`): Require live Fastmail token. Run with `make test-e2e`.
- Pattern: `@patch("fastmail_blade_mcp.server._get_client")` for server tool tests.
- Pattern: `mock_jmapc` fixture for client tests.

## Code conventions

- **Python 3.12+** — use modern syntax (PEP 604 unions, etc.)
- **Type hints everywhere** — mypy enforced
- **Ruff** for linting and formatting (line length 120)
- **FastMCP 2.0** — `@mcp.tool` decorator, `Annotated[type, Field(...)]` params
- **Token efficiency** — concise output default, limit= on lists, null omission
- **SSH commit signing** via 1Password (no GPG)
- **uv** as package manager, `uv.lock` committed
- Conventional-ish commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`

## Architecture notes

- JMAP client via `jmapc` library — lazy singleton, `asyncio.to_thread()`
- Write-gate: `FASTMAIL_WRITE_ENABLED` env var checked before all write tools
- Typed exception hierarchy maps JMAP error patterns to Python exceptions
- 18 tools across 7 categories: email read, email write, email manage, masked email, push, meta
- Masked Email via `jmapc` MaskedEmail extension
- Push via JMAP EventSource (bounded timeout, never blocks indefinitely)
