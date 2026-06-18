"""Unit tests for __init__.py — handlers and register()."""

import json
import importlib.util
import sys
from pathlib import Path

import pytest

# Load the couple_finance package from the hyphenated directory
pkg_dir = Path(__file__).resolve().parent.parent
init_path = pkg_dir / "__init__.py"
spec = importlib.util.spec_from_file_location(
    "couple_finance",
    str(init_path),
    submodule_search_locations=[str(pkg_dir)]
)
cf = importlib.util.module_from_spec(spec)
sys.modules["couple_finance"] = cf
spec.loader.exec_module(cf)


class MockCtx:
    """Mock Hermes plugin context that records register_tool calls."""

    def __init__(self):
        self.tools = []

    def register_tool(self, name, toolset, schema, handler):
        self.tools.append({
            "name": name,
            "toolset": toolset,
            "schema": schema,
            "handler": handler,
        })


@pytest.fixture
def mock_ctx():
    return MockCtx()


class TestRegister:
    def test_register_calls_six_tools(self, mock_ctx):
        """register() should call ctx.register_tool() exactly 6 times."""
        cf.register(mock_ctx)
        assert len(mock_ctx.tools) == 6

    def test_register_tool_names(self, mock_ctx):
        """All 6 tool names are registered correctly."""
        cf.register(mock_ctx)
        names = [t["name"] for t in mock_ctx.tools]
        assert "expense_add" in names
        assert "expense_list" in names
        assert "expense_report" in names
        assert "expense_delete" in names
        assert "expense_search" in names
        assert "expense_config" in names

    def test_register_toolset(self, mock_ctx):
        """All tools belong to the 'couple-finance' toolset."""
        cf.register(mock_ctx)
        for tool in mock_ctx.tools:
            assert tool["toolset"] == "couple-finance"

    def test_register_schemas_present(self, mock_ctx):
        """Each tool has a schema with name, description, and parameters."""
        cf.register(mock_ctx)
        for tool in mock_ctx.tools:
            schema = tool["schema"]
            assert "name" in schema
            assert "description" in schema
            assert "parameters" in schema

    def test_register_handlers_callable(self, mock_ctx):
        """Each registered handler is callable."""
        cf.register(mock_ctx)
        for tool in mock_ctx.tools:
            assert callable(tool["handler"])


class TestHandleExpenseAdd:
    def test_success(self, tmp_db_path):
        """Add expense returns ok=True with id."""
        result = cf._handle_expense_add({
            "amount": 100,
            "category": "餐飲",
            "payer": "Brian",
            "date": "2025-06-18",
            "split_method": "50/50",
            "note": "午餐",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert isinstance(data["id"], int)

    def test_missing_amount(self, tmp_db_path):
        """Missing required 'amount' returns error."""
        result = cf._handle_expense_add({
            "category": "餐飲",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert "error" in data


class TestHandleExpenseList:
    def test_default_list(self, tmp_db_path):
        """List returns expenses from the specified DB."""
        cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        result = cf._handle_expense_list({"base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["ok"] is True
        assert len(data["expenses"]) == 1

    def test_empty_db(self, tmp_db_path):
        """List on empty DB returns empty list."""
        result = cf._handle_expense_list({"base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["ok"] is True
        assert data["expenses"] == []


class TestHandleExpenseReport:
    def test_with_data(self, tmp_db_path):
        """Report returns by_category, by_payer, summary, owes."""
        cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        result = cf._handle_expense_report({
            "date_from": "2025-06-01", "date_to": "2025-06-30",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert "by_category" in data
        assert "by_payer" in data
        assert "summary" in data
        assert "owes" in data

    def test_empty_db(self, tmp_db_path):
        """Report on empty DB returns summary with default structure."""
        result = cf._handle_expense_report({
            "date_from": "2025-06-01", "date_to": "2025-06-30",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["by_category"] == []
        assert data["by_payer"] == []
        assert data["owes"] == []


class TestHandleExpenseDelete:
    def test_success(self, tmp_db_path):
        """Delete existing expense returns deleted=True."""
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]
        result = cf._handle_expense_delete({"expense_id": eid, "base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["ok"] is True
        assert data["deleted"] is True

    def test_nonexistent_id(self, tmp_db_path):
        """Delete nonexistent ID returns deleted=False."""
        result = cf._handle_expense_delete({"expense_id": 9999, "base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["ok"] is True
        assert data["deleted"] is False


class TestHandleExpenseSearch:
    def test_found(self, tmp_db_path):
        """Search finds expenses matching keyword."""
        cf._handle_expense_add({
            "amount": 800, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "火鍋聚餐",
            "base_dir": tmp_db_path,
        })
        result = cf._handle_expense_search({"keyword": "火鍋", "base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["ok"] is True
        assert len(data["results"]) >= 1

    def test_not_found(self, tmp_db_path):
        """Search with no matches returns empty list."""
        result = cf._handle_expense_search({"keyword": "不存在的關鍵字", "base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["ok"] is True
        assert data["results"] == []


class TestHandleExpenseConfig:
    def test_get_default(self, tmp_db_path):
        """Get default payer1 returns 'Brian'."""
        result = cf._handle_expense_config({"action": "get", "key": "payer1", "base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["ok"] is True
        assert data["value"] == "Brian"

    def test_set_and_get(self, tmp_db_path):
        """Set payer1 to '小明' then get it."""
        cf._handle_expense_config({"action": "set", "key": "payer1", "value": "小明", "base_dir": tmp_db_path})
        result = cf._handle_expense_config({"action": "get", "key": "payer1", "base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["value"] == "小明"

    def test_invalid_action(self, tmp_db_path):
        """Invalid action returns error."""
        result = cf._handle_expense_config({"action": "delete", "key": "payer1", "base_dir": tmp_db_path})
        data = json.loads(result)
        assert "error" in data
        assert "Unknown action" in data["error"]