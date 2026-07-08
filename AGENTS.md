# Couple Finance Plugin — Agent Guide

Hermes Agent plugin for couple expense tracking (記帳). Single plugin under `plugins/couple-finance/`.

## Structure

```
plugins/couple-finance/
  plugin.yaml        # Metadata: name, version, description
  __init__.py        # register(ctx) entry point, 7 tool schemas + handlers
  db.py              # SQLite schema, connection, CRUD (13 public functions)
  conftest.py        # Prevents pytest from collecting hyphenated dir as test module
  tests/
    __init__.py
    conftest.py      # Fixtures: tmp_db_path, fresh_db, MockCtx
    test_db.py       # Unit tests for db.py
    test_init.py     # Unit tests for handlers + register()
    test_integration.py  # E2E flow tests
```

## Running tests

```bash
# Full suite
python3 -m pytest plugins/couple-finance/tests/ -v

# Single file
python3 -m pytest plugins/couple-finance/tests/test_db.py -v

# Quick collection check (no execution)
python3 -m pytest plugins/couple-finance/tests/ --co -q
```

**pytest 9.0.3** is installed. No `pytest.ini`, `pyproject.toml`, or `setup.cfg` exists.

## Key quirks

- **Hyphenated package name** (`couple-finance/`): pytest cannot normally import it. Workarounds:
  - Root `conftest.py` in the plugin dir uses `pytest_ignore_collection` to skip the dir
  - `conftest.py` in `tests/` adds the plugin dir to `sys.path`
  - `test_init.py` and `test_integration.py` use `importlib.util.spec_from_file_location` to load `__init__.py`
- **Dual imports** in `__init__.py`: uses `try: from .db import ... / except ImportError: from db import ...` because import paths differ between Hermes runtime (relative) and pytest (absolute via sys.path hack)
- **`hermes_constants`** (`from hermes_constants import get_hermes_home`) is **not installed locally** — only available inside Hermes Agent. `db.py` has a try/except fallback to `Path.home() / ".hermes"` if the import fails.

## Test conventions

- **All tests use isolated temp databases** via `tmp_db_path` fixture — never `~/.hermes/`
- Every public db.py function is tested with ≥1 happy-path test
- `compute_owes` is the most complex function — 12+ tests cover: 50/50, 60/40, 各付各, empty split, negative amounts, zero-share splits, multi-entry accumulation, unknown payer, invalid split string, date range, deleted exclusion
- `edit_expense` is a PATCH-style partial update: returns `(new_row, changes_dict)` with a diff of only changed fields; handler wraps this as a `"diff"` key in the JSON response
- Soft-delete consistency: every query function (`list_expenses`, `report_*`, `search_expenses`, `compute_owes`) must exclude `is_deleted=1` records by default
- Handlers are tested through `cf._handle_*()` calls (not via Hermes), always passing `base_dir` as a param not exposed in tool schemas
- MockCtx records `register_tool()` calls — used to verify tool registration without Hermes
- No external test dependencies (no pytest-mock, factory_boy, etc.)

## Database

- SQLite with WAL mode and foreign keys enabled
- Tables: `expenses` (id, date, amount, category, payer, split_method, note, is_deleted, created_at, updated_at, edit_reason), `config` (key, value)
- FTS5 virtual table (`expenses_fts`) for full-text search on `note` + `category` — **only if SQLite compiled with FTS5**; runtime fallback to `LIKE` queries
- Soft delete via `is_deleted=1` flag — all query functions exclude deleted by default
- `config` table stores payer names (`payer1`, `payer2` defaults: Brian, Partner) and arbitrary k/v
- DB auto-created at `get_hermes_home() / "couple-finance.db"` on first connection
- `base_dir` parameter allows overriding the DB location (used in tests)

## Commands

```bash
# Run all tests (no config file needed — pytest auto-discovers)
python3 -m pytest plugins/couple-finance/tests/ -v

# Git: conventional commits used (feat, fix, test)
git commit -m "feat(plugin): description"
git commit -m "fix: description"
git commit -m "test(couple-finance): description"
```

## Architecture notes

- The plugin has **7 registered tools**: `expense_add`, `expense_list`, `expense_report`, `expense_delete`, `expense_edit`, `expense_search`, `expense_config`
- All tool handlers return `json.dumps({"ok": True, ...})` or `json.dumps({"error": str(e)})`
- `base_dir` param exists on all handlers/db functions but is **not in tool schemas** — it's test-only infrastructure
- No linter, formatter, or type checker configuration exists
- `.gitignore` ensures `.sisyphus/` and `__pycache__/` are never committed
