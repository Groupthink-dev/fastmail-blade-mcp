# Changelog

## 0.2.0 — 2026-05-23

### Changed

- **DD-338 Phase B.1.b — stable sort-before-return on 2 multi-record read tools.**
  - `fastmail_identities`: sort by `id` asc before formatter.
  - `mail_mailboxes`: sort by `sort_order` asc (None placed at tail via 9999
    sentinel per architect lock #6), then `name` asc, then `id` asc tie-break
    before formatter. JMAP `sortOrder` attribute on `jmapc.Mailbox` verified at
    branch checkout — exposed as `sort_order` (Python snake_case) per
    `jmapc.models.mailbox.Mailbox`; default value is `0`.
- **Catalog declaration**: `granularity.deterministic_ordering` flips
  `unstable → stable` on both tools in `stallari-plugins` catalog entry.
- **Tool descriptions** updated to document the chosen sort key per tool.

### Added

- **7 new pytest cases** in `tests/test_b1b_determinism.py` — N=5 byte-identical
  determinism harness per tool + sort-key invariance + None-sort-order tail
  placement + empty-input.

### Fixed

- `__init__.py` `__version__` brought into alignment with `pyproject.toml`
  (`0.1.0 → 0.2.0`); prior drift was a pre-existing issue.
