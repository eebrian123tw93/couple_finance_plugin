# Couple Finance Plugin

A Hermes Agent plugin for shared expense tracking between couples. Built with SQLite, zero external dependencies.

## Overview

Couple Finance is a Hermes Agent plugin that lets couples track shared expenses through natural language. Tell the agent "dinner 850, I paid" and it records a structured expense entry. Ask "how much did we spend this month" and it returns an aggregated report with who-owes-whom calculations.

### Features

- **7 Hermes tools**: `expense_add`, `expense_list`, `expense_report`, `expense_delete`, `expense_edit`, `expense_search`, `expense_config`
- **Natural language interface**: the LLM auto-fills category, payer, and amount from casual speech
- **Flexible split methods**: 50/50, 60/40, each-pays-own, or custom ratios
- **Owes computation**: automatically calculates who owes whom based on split rules
- **Full-text search**: FTS5-powered search on notes and categories (falls back to LIKE if unavailable)
- **Soft delete**: expenses are preserved in the database but excluded from queries
- **Configurable payers**: customize payer names
- **No external dependencies**: Python stdlib only (`sqlite3`, `json`, `pathlib`)
- **Test suite**: 148 tests with isolated temp databases

### Requirements

- Python 3.10+
- Hermes Agent (for runtime)
- `pytest` 9.0.3 (for running tests)

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd couple_finance_plugin

# 2. Copy the plugin to Hermes plugins directory
mkdir -p ~/.hermes/plugins
cp -r plugins/couple-finance ~/.hermes/plugins/couple-finance

# 3. Enable the plugin and toolset in ~/.hermes/config.yaml
#    plugins:
#      enabled:
#        - couple-finance
#    toolsets:
#      - couple-finance
```

### Usage

The plugin registers 7 tools under the `couple-finance` toolset:

| Tool | Description |
|------|-------------|
| `expense_add` | Record an expense (amount, category①, payer, split method, note) |
| `expense_list` | List expenses with filters (date range, category, payer, pagination) |
| `expense_report` | Aggregated report by category, by payer, summary, and owes calculation |
| `expense_delete` | Soft-delete an expense by ID |
| `expense_edit` | PATCH-style partial update of an expense; returns the updated record plus a diff of changed fields |
| `expense_search` | Full-text search across notes and categories |
| `expense_config` | Get or set configuration (payer names, etc.) |

① Categories: dining, transport, shopping, entertainment, housing, utilities, medical, education, other

**Example conversation with the agent:**

> User: "dinner 850, I paid"  
> Agent calls `expense_add(amount=850, category="dining", payer="Alice", split_method="50/50", note="dinner")`

> User: "how much did we spend this month"  
> Agent calls `expense_report()` → returns category totals, payer totals, and who owes whom

> User: "fix that dinner to 950 and change category to dining"  
> Agent calls `expense_edit(expense_id=3, amount=950, category="dining")` → returns updated record + `{"diff": {"amount": {"old": 850.0, "new": 950.0}, "category": {"old": "交通", "new": "餐飲"}}}`

### Running Tests

```bash
# Full suite
python3 -m pytest plugins/couple-finance/tests/ -v

# Single test file
python3 -m pytest plugins/couple-finance/tests/test_db.py -v
```

All tests use isolated temporary databases — never writes to your production DB.

### Project Structure

```
plugins/couple-finance/
  plugin.yaml          # Plugin metadata
  __init__.py          # Entry point: register() + 7 tool handlers
  db.py                # SQLite schema, connection, CRUD (13 public functions)
  conftest.py          # Pytest collection workaround for hyphenated dir
  tests/
    conftest.py        # Fixtures: tmp_db_path, fresh_db, MockCtx
    test_db.py         # Unit tests for db.py
    test_init.py       # Unit tests for handlers + register()
    test_integration.py # End-to-end flow tests
```

### Database

- **Engine**: SQLite with WAL mode and foreign keys enabled
- **Tables**: `expenses` (soft-delete via `is_deleted` flag), `config` (key-value settings)
- **FTS5**: Full-text search on notes and categories; runtime fallback to `LIKE` if FTS5 unavailable
- **Path**: Auto-created at `~/.hermes/couple-finance.db` (overridable via `base_dir` parameter in code)

### Architecture Notes

- All handlers return `json.dumps({"ok": True, ...})` on success, `json.dumps({"error": str(e)})` on failure
- The `base_dir` parameter on handlers and db functions is test-only infrastructure — not exposed in tool schemas
- The hyphenated directory name (`couple-finance/`) requires import workarounds for pytest; see `conftest.py` and the dual-import pattern in `__init__.py`
- `expense_edit` is a PATCH-style partial update — only provided fields are changed; the response includes a `"diff"` object showing only what changed

### AI-Assisted Development

This project was developed with the assistance of [OpenCode](https://opencode.cloud), an AI-powered coding agent (Sisyphus) working under the orchestration of OhMyOpenCode. Key architectural decisions, code generation, test writing, and documentation were produced through human-AI collaboration.

## Support

If you find this plugin useful, consider supporting its development:

[<img src="https://cdn.prod.website-files.com/5c14e387dab576fe667689cf/670f5a01c01ea9191809398c_support_me_on_kofi_blue.avif" alt="Support me on Ko-fi" width="200">](https://ko-fi.com/eebrian123tw93)

## License

MIT
