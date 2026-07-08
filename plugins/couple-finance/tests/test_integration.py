"""End-to-end integration tests for couple-finance plugin."""

import json
import importlib.util
import sys
from pathlib import Path

# Load the couple_finance package from the hyphenated directory (hyphenated dir needs importlib)
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

# Direct imports for db functions (conftest adds couple-finance/ to sys.path)
from db import (  # noqa: E402
    add_expense, list_expenses, delete_expense, search_expenses,
    report_by_category, report_by_payer, report_summary, compute_owes,
    get_config, set_config, get_connection, edit_expense,
)


class TestE2EFullFlow:
    """Simulate a complete day of couple finance usage."""

    def test_full_day_flow(self, tmp_db_path):
        _eid1 = add_expense("2025-06-18", 85, "餐飲", "Brian", "50/50", "早餐", base_dir=tmp_db_path)
        _eid2 = add_expense("2025-06-18", 120, "餐飲", "Partner", "50/50", "午餐", base_dir=tmp_db_path)
        _eid3 = add_expense("2025-06-18", 800, "餐飲", "Brian", "60/40", "火鍋", base_dir=tmp_db_path)

        all_expenses = list_expenses(base_dir=tmp_db_path)
        assert len(all_expenses) == 3

        dining = list_expenses(category="餐飲", base_dir=tmp_db_path)
        assert len(dining) == 3

        by_cat = report_by_category("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        cat_dict = {r["category"]: r for r in by_cat}
        assert "餐飲" in cat_dict
        assert cat_dict["餐飲"]["total"] == 85 + 120 + 800

        results = search_expenses("火鍋", base_dir=tmp_db_path)
        assert len(results) >= 1
        assert any(r["note"] == "火鍋" for r in results)

        deleted = delete_expense(_eid1, base_dir=tmp_db_path)
        assert deleted is True

        remaining = list_expenses(base_dir=tmp_db_path)
        assert len(remaining) == 2

        by_cat2 = report_by_category("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        cat_dict2 = {r["category"]: r for r in by_cat2}
        assert cat_dict2["餐飲"]["total"] == 120 + 800

        results2 = search_expenses("火鍋", base_dir=tmp_db_path)
        assert len(results2) >= 1


class TestE2EConfigFlow:
    """Test config customization and persistence."""

    def test_customize_payers_and_owes(self, tmp_db_path):
        set_config("payer1", "小明", base_dir=tmp_db_path)
        set_config("payer2", "小華", base_dir=tmp_db_path)

        row1 = get_config("payer1", base_dir=tmp_db_path)
        assert row1["value"] == "小明"

        add_expense("2025-06-18", 100, "餐飲", "小明", "50/50", "晚餐", base_dir=tmp_db_path)

        owes = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(owes) == 1
        assert owes[0]["from"] == "小華"
        assert owes[0]["to"] == "小明"

    def test_config_persists_across_connections(self, tmp_db_path):
        set_config("payer1", "Alice", base_dir=tmp_db_path)
        conn2 = get_connection(base_dir=tmp_db_path)
        row = conn2.execute("SELECT value FROM config WHERE key='payer1'").fetchone()
        assert dict(row)["value"] == "Alice"
        conn2.close()


class TestE2ESoftDeleteConsistency:
    """Verify soft-deleted expenses are excluded from ALL query functions."""

    def test_soft_delete_excluded_everywhere(self, tmp_db_path):
        _eid_keep = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "keep this", base_dir=tmp_db_path)
        eid_del = add_expense("2025-06-01", 200, "交通", "Partner", "50/50", "delete this", base_dir=tmp_db_path)
        delete_expense(eid_del, base_dir=tmp_db_path)

        items = list_expenses(base_dir=tmp_db_path)
        assert len(items) == 1
        assert items[0]["note"] == "keep this"

        all_items = list_expenses(include_deleted=True, base_dir=tmp_db_path)
        assert len(all_items) == 2

        by_cat = report_by_category("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(by_cat) == 1
        assert by_cat[0]["category"] == "餐飲"

        by_payer = report_by_payer("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(by_payer) == 1
        assert by_payer[0]["payer"] == "Brian"

        summary = report_summary("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert summary["total_amount"] == 100.0
        assert summary["total_count"] == 1

        results = search_expenses("delete", base_dir=tmp_db_path)
        assert len(results) == 0

        owes = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(owes) == 1
        assert owes[0]["amount"] == 50.0


class TestE2EEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_negative_amount_refund(self, tmp_db_path):
        add_expense("2025-06-01", 200, "餐飲", "Brian", "50/50", "晚餐", base_dir=tmp_db_path)
        add_expense("2025-06-01", -50, "餐飲", "Brian", "50/50", "退款", base_dir=tmp_db_path)

        summary = report_summary("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert summary["total_amount"] == 150.0
        assert summary["total_count"] == 2

    def test_empty_db_all_operations(self, tmp_db_path):
        items = list_expenses(base_dir=tmp_db_path)
        assert items == []

        by_cat = report_by_category("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert by_cat == []

        by_payer = report_by_payer("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert by_payer == []

        summary = report_summary("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert summary is not None
        assert summary["total_amount"] is None
        assert summary["total_count"] == 0

        results = search_expenses("anything", base_dir=tmp_db_path)
        assert results == []

        owes = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert owes == []

    def test_default_category_when_missing(self, tmp_db_path):
        result = cf._handle_expense_add({
            "amount": 50,
            "date": "2025-06-18",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        assert data["ok"] is True
        items = list_expenses(base_dir=tmp_db_path)
        assert items[0]["category"] == "其他"


class TestE2EBilingual:
    """End-to-end test for bilingual category support."""

    def test_english_input_chinese_storage(self, tmp_db_path):
        add_expense("2025-06-18", 85, "dining", "Brian", "50/50", "breakfast", base_dir=tmp_db_path)
        add_expense("2025-06-18", 200, "transport", "Partner", "each-pays-own", "taxi", base_dir=tmp_db_path)
        add_expense("2025-06-18", 800, "dining", "Brian", "60/40", "hotpot", base_dir=tmp_db_path)

        all_expenses = list_expenses(base_dir=tmp_db_path)
        assert len(all_expenses) == 3
        assert all_expenses[0]["category"] == "dining"
        assert all_expenses[1]["category"] == "transport"
        assert all_expenses[2]["category"] == "dining"

        by_cat = report_by_category("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        cat_dict = {r["category"]: r for r in by_cat}
        assert "dining" in cat_dict
        assert "transport" in cat_dict
        assert cat_dict["dining"]["total"] == 85 + 800

    def test_english_category_filter(self, tmp_db_path):
        add_expense("2025-06-18", 85, "dining", "Brian", "50/50", "breakfast", base_dir=tmp_db_path)
        add_expense("2025-06-18", 200, "transport", "Partner", "50/50", "taxi", base_dir=tmp_db_path)

        dining = list_expenses(category="dining", base_dir=tmp_db_path)
        assert len(dining) == 1

    def test_report_english_output(self, tmp_db_path):
        set_config("language", "en", base_dir=tmp_db_path)
        add_expense("2025-06-18", 100, "dining", "Brian", "50/50", "lunch", base_dir=tmp_db_path)

        result = cf._handle_expense_report({
            "date_from": "2025-06-01", "date_to": "2025-06-30",
            "base_dir": tmp_db_path,
        })
        data = json.loads(result)
        for item in data["by_category"]:
            assert item["category"] == "dining"

    def test_owes_skip_each_pays_own(self, tmp_db_path):
        add_expense("2025-06-18", 100, "dining", "Brian", "each-pays-own", "lunch", base_dir=tmp_db_path)
        add_expense("2025-06-18", 200, "dining", "Brian", "50/50", "dinner", base_dir=tmp_db_path)

        owes = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(owes) == 1
        assert owes[0]["amount"] == 100.0


class TestE2EEditFlow:
    """End-to-end tests for expense editing flow."""

    def test_add_edit_report_flow(self, tmp_db_path):
        eid = add_expense("2025-06-18", 100, "餐飲", "Brian", "50/50", "晚餐", base_dir=tmp_db_path)
        edit_expense(eid, amount=200, base_dir=tmp_db_path)
        by_cat = report_by_category("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        cat_dict = {r["category"]: r for r in by_cat}
        assert "餐飲" in cat_dict
        assert cat_dict["餐飲"]["total"] == 200.0

    def test_edit_soft_deleted_consistency(self, tmp_db_path):
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "deleted expense", base_dir=tmp_db_path)
        delete_expense(eid, base_dir=tmp_db_path)
        edit_expense(eid, amount=200, base_dir=tmp_db_path)

        items = list_expenses(base_dir=tmp_db_path)
        assert len(items) == 0

        by_cat = report_by_category("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(by_cat) == 0

        results = search_expenses("deleted", base_dir=tmp_db_path)
        assert len(results) == 0

        owes = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(owes) == 0

        all_items = list_expenses(include_deleted=True, base_dir=tmp_db_path)
        assert len(all_items) == 1
        assert all_items[0]["is_deleted"] == 1
        assert all_items[0]["amount"] == 200.0

    def test_edit_then_search_consistency(self, tmp_db_path):
        eid = add_expense("2025-06-18", 50, "餐飲", "Brian", "50/50", "oldnote", base_dir=tmp_db_path)
        edit_expense(eid, note="newnote", base_dir=tmp_db_path)

        old_results = search_expenses("oldnote", base_dir=tmp_db_path)
        assert len(old_results) == 0

        new_results = search_expenses("newnote", base_dir=tmp_db_path)
        assert len(new_results) >= 1
        assert any(r["note"] == "newnote" for r in new_results)

    def test_edit_multiple_times(self, tmp_db_path):
        eid = add_expense("2025-06-18", 100, "餐飲", "Brian", "50/50", "multi-edit", base_dir=tmp_db_path)

        edit_expense(eid, amount=150, base_dir=tmp_db_path)
        items = list_expenses(base_dir=tmp_db_path)
        assert items[0]["amount"] == 150.0

        first_updated = items[0].get("updated_at")

        edit_expense(eid, amount=300, base_dir=tmp_db_path)
        items = list_expenses(base_dir=tmp_db_path)
        assert items[0]["amount"] == 300.0
        assert items[0].get("updated_at") is not None

    def test_edit_category_report_grouping(self, tmp_db_path):
        eid = add_expense("2025-06-18", 100, "餐飲", "Brian", "50/50", "category change", base_dir=tmp_db_path)
        edit_expense(eid, category="交通", base_dir=tmp_db_path)

        by_cat = report_by_category("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        cat_dict = {r["category"]: r for r in by_cat}
        assert "交通" in cat_dict
        assert cat_dict["交通"]["total"] == 100.0
        assert "餐飲" not in cat_dict
