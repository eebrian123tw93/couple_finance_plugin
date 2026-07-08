"""Unit tests for __init__.py — handlers and register()."""

import json
import importlib.util
import sys
from pathlib import Path

import pytest

# Load the couple_finance package from the hyphenated directory.
pkg_dir = Path(__file__).resolve().parent.parent  # couple-finance/
init_path = pkg_dir / "__init__.py"

spec = importlib.util.spec_from_file_location(
    "couple_finance",
    str(init_path),
    submodule_search_locations=[str(pkg_dir)],
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
def tmp_db_path(tmp_path):
    """Return a temporary directory path for isolated DB testing."""
    return str(tmp_path)


@pytest.fixture
def mock_ctx():
    """Provide a MockCtx instance for testing register()."""
    return MockCtx()


# ===================================================================
# register() tests
# ===================================================================

class TestRegister:
    def test_register_calls_seven_tools(self, mock_ctx):
        cf.register(mock_ctx)
        assert len(mock_ctx.tools) == 7

    def test_register_tool_names(self, mock_ctx):
        cf.register(mock_ctx)
        names = [t["name"] for t in mock_ctx.tools]
        assert "expense_add" in names
        assert "expense_list" in names
        assert "expense_report" in names
        assert "expense_delete" in names
        assert "expense_search" in names
        assert "expense_config" in names
        assert "expense_edit" in names

    def test_register_toolset(self, mock_ctx):
        cf.register(mock_ctx)
        for tool in mock_ctx.tools:
            assert tool["toolset"] == "couple-finance"

    def test_register_schemas_present(self, mock_ctx):
        cf.register(mock_ctx)
        for tool in mock_ctx.tools:
            schema = tool["schema"]
            assert "name" in schema
            assert "description" in schema
            assert "parameters" in schema

    def test_register_handlers_callable(self, mock_ctx):
        cf.register(mock_ctx)
        for tool in mock_ctx.tools:
            assert callable(tool["handler"])


# ===================================================================
# _handle_expense_add tests
# ===================================================================

class TestHandleExpenseAdd:
    def test_success(self, tmp_db_path):
        result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert isinstance(data["id"], int)

    def test_missing_amount(self, tmp_db_path):
        result = cf._handle_expense_add({
            "category": "餐飲", "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert "error" in data

    def test_defaults(self, tmp_db_path):
        result = cf._handle_expense_add({"amount": 50, "base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["ok"] is True

    def test_multiple_adds(self, tmp_db_path):
        r1 = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        r2 = cf._handle_expense_add({
            "amount": 200, "category": "交通", "payer": "Partner",
            "date": "2025-06-19", "split_method": "各付各", "note": "計程車",
            "base_dir": tmp_db_path,
        })
        d1 = json.loads(r1)
        d2 = json.loads(r2)
        assert d1["id"] < d2["id"]


# ===================================================================
# _handle_expense_list tests
# ===================================================================

class TestHandleExpenseList:
    def test_default_list(self, tmp_db_path):
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
        result = cf._handle_expense_list({"base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["ok"] is True
        assert data["expenses"] == []

    def test_filter_by_category(self, tmp_db_path):
        cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        cf._handle_expense_add({
            "amount": 200, "category": "交通", "payer": "Partner",
            "date": "2025-06-19", "split_method": "各付各", "note": "計程車",
            "base_dir": tmp_db_path,
        })
        result = cf._handle_expense_list({
            "category": "餐飲", "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert len(data["expenses"]) == 1
        assert data["expenses"][0]["category"] == "餐飲"

    def test_filter_by_date_range(self, tmp_db_path):
        cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        cf._handle_expense_add({
            "amount": 200, "category": "交通", "payer": "Partner",
            "date": "2025-07-19", "split_method": "各付各", "note": "計程車",
            "base_dir": tmp_db_path,
        })
        result = cf._handle_expense_list({
            "date_from": "2025-06-01", "date_to": "2025-06-30",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert len(data["expenses"]) == 1

    def test_deleted_excluded(self, tmp_db_path):
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]
        cf._handle_expense_delete({"expense_id": eid, "base_dir": tmp_db_path})
        result = cf._handle_expense_list({"base_dir": tmp_db_path})
        data = json.loads(result)
        assert len(data["expenses"]) == 0


# ===================================================================
# _handle_expense_report tests
# ===================================================================

class TestHandleExpenseReport:
    def test_with_data(self, tmp_db_path):
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
        result = cf._handle_expense_report({
            "date_from": "2025-06-01", "date_to": "2025-06-30",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["summary"]["total_count"] == 0

    def test_by_category_totals(self, tmp_db_path):
        cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        cf._handle_expense_add({
            "amount": 200, "category": "餐飲", "payer": "Partner",
            "date": "2025-06-19", "split_method": "各付各", "note": "晚餐",
            "base_dir": tmp_db_path,
        })
        result = cf._handle_expense_report({
            "date_from": "2025-06-01", "date_to": "2025-06-30",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        categories = {item["category"]: item for item in data["by_category"]}
        assert "餐飲" in categories
        assert categories["餐飲"]["total"] == 300

    def test_owes_calculation(self, tmp_db_path):
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
        assert len(data["owes"]) >= 1
        assert any(o["to"] == "Brian" for o in data["owes"])


# ===================================================================
# _handle_expense_delete tests
# ===================================================================

class TestHandleExpenseDelete:
    def test_success(self, tmp_db_path):
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
        result = cf._handle_expense_delete({"expense_id": 9999, "base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["ok"] is True
        assert data["deleted"] is False

    def test_double_delete(self, tmp_db_path):
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]

        r1 = cf._handle_expense_delete({"expense_id": eid, "base_dir": tmp_db_path})
        assert json.loads(r1)["deleted"] is True

        r2 = cf._handle_expense_delete({"expense_id": eid, "base_dir": tmp_db_path})
        assert json.loads(r2)["deleted"] is False


# ===================================================================
# _handle_expense_search tests
# ===================================================================

class TestHandleExpenseSearch:
    def test_found(self, tmp_db_path):
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
        result = cf._handle_expense_search({
            "keyword": "不存在的關鍵字", "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["results"] == []

    def test_search_by_category(self, tmp_db_path):
        cf._handle_expense_add({
            "amount": 800, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        result = cf._handle_expense_search({"keyword": "餐飲", "base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["ok"] is True
        assert len(data["results"]) >= 1

    def test_deleted_excluded(self, tmp_db_path):
        cf._handle_expense_add({
            "amount": 800, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "火鍋聚餐",
            "base_dir": tmp_db_path,
        })
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]
        cf._handle_expense_delete({"expense_id": eid, "base_dir": tmp_db_path})

        result = cf._handle_expense_search({"keyword": "午餐", "base_dir": tmp_db_path})
        data = json.loads(result)
        assert data["ok"] is True
        for r in data["results"]:
            assert r.get("note") != "午餐"


# ===================================================================
# _handle_expense_config tests
# ===================================================================

class TestHandleExpenseConfig:
    def test_get_default(self, tmp_db_path):
        result = cf._handle_expense_config({
            "action": "get", "key": "payer1", "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["value"] == "Brian"

    def test_get_payer2_default(self, tmp_db_path):
        result = cf._handle_expense_config({
            "action": "get", "key": "payer2", "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["value"] == "Partner"

    def test_set_and_get(self, tmp_db_path):
        cf._handle_expense_config({
            "action": "set", "key": "payer1", "value": "小明", "base_dir": tmp_db_path,
        })
        result = cf._handle_expense_config({
            "action": "get", "key": "payer1", "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["value"] == "小明"

    def test_set_returns_updated(self, tmp_db_path):
        result = cf._handle_expense_config({
            "action": "set", "key": "payer1", "value": "TestUser", "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["updated"] is True

    def test_invalid_action(self, tmp_db_path):
        result = cf._handle_expense_config({
            "action": "delete", "key": "payer1", "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert "error" in data
        assert "Unknown action" in data["error"]

    def test_get_nonexistent_key(self, tmp_db_path):
        result = cf._handle_expense_config({
            "action": "get", "key": "nonexistent_key", "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["value"] is None


# ===================================================================
# Bilingual category tests
# ===================================================================

class TestHandleBilingualCategories:
    """Handlers accept English category names and normalize to Chinese."""

    def test_add_with_english_category(self, tmp_db_path):
        result = cf._handle_expense_add({
            "amount": 100, "category": "dining", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "lunch",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        list_result = cf._handle_expense_list({"base_dir": tmp_db_path})
        list_data = json.loads(list_result)
        assert list_data["expenses"][0]["category"] == "餐飲"

    def test_add_with_mixed_case_english_category(self, tmp_db_path):
        result = cf._handle_expense_add({
            "amount": 200, "category": "Transport", "payer": "Partner",
            "date": "2025-06-18", "split_method": "50/50", "note": "taxi",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        list_result = cf._handle_expense_list({"base_dir": tmp_db_path})
        list_data = json.loads(list_result)
        assert list_data["expenses"][0]["category"] == "交通"

    def test_list_filter_by_english_category(self, tmp_db_path):
        cf._handle_expense_add({
            "amount": 100, "category": "dining", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "lunch",
            "base_dir": tmp_db_path,
        })
        result = cf._handle_expense_list({
            "category": "dining", "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert len(data["expenses"]) == 1

    def test_report_respects_language_config_en(self, tmp_db_path):
        cf._handle_expense_config({
            "action": "set", "key": "language", "value": "en", "base_dir": tmp_db_path,
        })
        cf._handle_expense_add({
            "amount": 100, "category": "dining", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "lunch",
            "base_dir": tmp_db_path,
        })
        result = cf._handle_expense_report({
            "date_from": "2025-06-01", "date_to": "2025-06-30",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        for item in data["by_category"]:
            assert item["category"] == "dining"

    def test_report_respects_language_config_zh(self, tmp_db_path):
        cf._handle_expense_config({
            "action": "set", "key": "language", "value": "zh", "base_dir": tmp_db_path,
        })
        cf._handle_expense_add({
            "amount": 100, "category": "dining", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "lunch",
            "base_dir": tmp_db_path,
        })
        result = cf._handle_expense_report({
            "date_from": "2025-06-01", "date_to": "2025-06-30",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        for item in data["by_category"]:
            assert item["category"] == "餐飲"


# ===================================================================
# _handle_expense_edit tests
# ===================================================================

class TestHandleExpenseEdit:

    def test_success_returns_expense_and_diff(self, tmp_db_path):
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]

        result = cf._handle_expense_edit({
            "expense_id": eid, "amount": 200, "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["id"] == eid
        assert "expense" in data
        assert data["expense"]["amount"] == 200
        assert "diff" in data
        assert data["diff"]["amount"]["old"] == 100
        assert data["diff"]["amount"]["new"] == 200

    def test_edit_multiple_fields(self, tmp_db_path):
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]

        result = cf._handle_expense_edit({
            "expense_id": eid, "amount": 200, "note": "晚餐",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["expense"]["amount"] == 200
        assert data["expense"]["note"] == "晚餐"

    def test_edit_preserves_omitted_fields(self, tmp_db_path):
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]

        result = cf._handle_expense_edit({
            "expense_id": eid, "amount": 200, "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["expense"]["category"] == "餐飲"
        assert data["expense"]["payer"] == "Brian"
        assert data["expense"]["split_method"] == "50/50"

    def test_edit_with_reason(self, tmp_db_path):
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]

        result = cf._handle_expense_edit({
            "expense_id": eid, "amount": 200, "reason": "corrected",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["expense"]["edit_reason"] == "corrected"

    def test_no_fields_error(self, tmp_db_path):
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]

        result = cf._handle_expense_edit({
            "expense_id": eid, "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert "error" in data

    def test_only_reason_error(self, tmp_db_path):
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]

        result = cf._handle_expense_edit({
            "expense_id": eid, "reason": "just a note",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert "error" in data

    def test_nonexistent_id_error(self, tmp_db_path):
        result = cf._handle_expense_edit({
            "expense_id": 9999, "amount": 200, "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert "error" in data

    def test_category_normalized(self, tmp_db_path):
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]

        result = cf._handle_expense_edit({
            "expense_id": eid, "category": "dining", "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["expense"]["category"] == "餐飲"

    def test_edit_soft_deleted(self, tmp_db_path):
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]

        cf._handle_expense_delete({"expense_id": eid, "base_dir": tmp_db_path})

        result = cf._handle_expense_edit({
            "expense_id": eid, "amount": 200, "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        assert data["expense"]["is_deleted"] == 1

    def test_edit_then_list_reflects_changes(self, tmp_db_path):
        add_result = cf._handle_expense_add({
            "amount": 100, "category": "餐飲", "payer": "Brian",
            "date": "2025-06-18", "split_method": "50/50", "note": "午餐",
            "base_dir": tmp_db_path,
        })
        eid = json.loads(add_result)["id"]

        cf._handle_expense_edit({
            "expense_id": eid, "amount": 300, "base_dir": tmp_db_path,
        })

        list_result = cf._handle_expense_list({"base_dir": tmp_db_path})
        list_data = json.loads(list_result)
        assert len(list_data["expenses"]) >= 1
        assert any(e["amount"] == 300 for e in list_data["expenses"])
