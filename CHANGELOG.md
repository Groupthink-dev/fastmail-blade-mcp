# Changelog

## 0.4.0 — 2026-05-24

### Changed

- **DD-338 Phase E.python — depend on `stallari-mcp-helpers>=0.1.0,<1.0.0`.**
  - Removed local `_format_meta_envelope` + `_append_meta` helpers from
    `formatters.py`; canonical `meta_envelope` + `append_meta` are now
    re-exported from the lib for backward call-site compatibility.
  - Renamed all `_format_meta_envelope` / `_append_meta` call-sites in
    `server.py` (5 tools × 2 helpers = 10 sites) to canonical names.
- **Wire-shape change** (test fixtures updated to match canonical):
  - `_meta.filtered_by` is sorted alphabetically inside the helper (unchanged
    semantically — was already sorted by the previous local helper).
  - `_meta.redactions` is now always present (defaults to `[]`); previously
    omitted when empty.
  - `_meta.next_cursor` is now always present (defaults to `null`); previously
    omitted when `None`.
  - JSON separators tightened from loose `(", ", ": ")` to canonical
    `(",", ":")` — the JSON payload parses identically; only the rendered
    byte representation differs.
  - `_meta.error_notes` and `_meta.domain_hints` (new lib field) remain
    conditionally included only when non-empty.

### Notes

- Pure substrate swap — no behavioural change to any tool. Pack-spec catalog
  declarations unchanged.
- `mypy` config gains a per-module override suppressing `warn_return_any` on
  modules that call lib helpers; the lib ships annotations but no `py.typed`
  marker at `v0.1.0`. Remove the override once the lib ships `py.typed`.

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
