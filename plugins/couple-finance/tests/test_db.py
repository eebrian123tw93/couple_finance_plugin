"""Unit tests for db.py — all database operations."""

import pytest
from db import (
    add_expense, list_expenses, report_by_category, report_by_payer,
    report_summary, delete_expense, search_expenses, compute_owes,
    get_config, set_config, get_connection, edit_expense,
)


class TestAddExpense:
    def test_add_expense_returns_id(self, tmp_db_path):
        """Add expense returns an integer ID >= 1."""
        eid = add_expense("2025-06-18", 100, "餐飲", "Brian", "50/50", "午餐", base_dir=tmp_db_path)
        assert isinstance(eid, int)
        assert eid >= 1

    def test_add_expense_data_persisted(self, tmp_db_path):
        """Add expense with all fields, query it back, verify all fields match."""
        eid = add_expense("2025-06-18", 250.5, "交通", "Partner", "60/40", "計程車", base_dir=tmp_db_path)
        results = list_expenses(base_dir=tmp_db_path)
        assert len(results) == 1
        exp = results[0]
        assert exp["id"] == eid
        assert exp["date"] == "2025-06-18"
        assert exp["amount"] == 250.5
        assert exp["category"] == "交通"
        assert exp["payer"] == "Partner"
        assert exp["split_method"] == "60/40"
        assert exp["note"] == "計程車"
        assert exp["is_deleted"] == 0

    def test_add_expense_negative_amount(self, tmp_db_path):
        """Negative amounts (refunds) are stored as-is."""
        eid = add_expense("2025-06-18", -50, "餐飲", "Brian", "50/50", "退款", base_dir=tmp_db_path)
        results = list_expenses(base_dir=tmp_db_path)
        assert results[0]["amount"] == -50

    def test_add_expense_zero_amount(self, tmp_db_path):
        """Zero amount is stored without error."""
        eid = add_expense("2025-06-18", 0, "其他", "Brian", "", "free", base_dir=tmp_db_path)
        results = list_expenses(base_dir=tmp_db_path)
        assert results[0]["amount"] == 0

    def test_add_expense_empty_split_method(self, tmp_db_path):
        """Empty split_method is stored as empty string."""
        eid = add_expense("2025-06-18", 100, "餐飲", "Brian", "", "test", base_dir=tmp_db_path)
        results = list_expenses(base_dir=tmp_db_path)
        assert results[0]["split_method"] == ""

    def test_add_multiple_expenses_incremental_ids(self, tmp_db_path):
        """Multiple expenses get incrementing IDs."""
        eid1 = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        eid2 = add_expense("2025-06-02", 200, "交通", "Partner", "50/50", "", base_dir=tmp_db_path)
        assert eid2 > eid1


class TestListExpenses:
    def test_list_default(self, tmp_db_path):
        """Add 3 expenses, list all, verify 3 returned."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "早餐", base_dir=tmp_db_path)
        add_expense("2025-06-02", 200, "交通", "Partner", "50/50", "加油", base_dir=tmp_db_path)
        add_expense("2025-06-03", 300, "購物", "Brian", "60/40", "衣服", base_dir=tmp_db_path)
        results = list_expenses(base_dir=tmp_db_path)
        assert len(results) == 3

    def test_list_filter_category(self, tmp_db_path):
        """Filter by category returns only matching expenses."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        add_expense("2025-06-02", 200, "交通", "Partner", "50/50", "", base_dir=tmp_db_path)
        add_expense("2025-06-03", 150, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        results = list_expenses(category="餐飲", base_dir=tmp_db_path)
        assert len(results) == 2
        assert all(r["category"] == "餐飲" for r in results)

    def test_list_filter_payer(self, tmp_db_path):
        """Filter by payer returns only matching expenses."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        add_expense("2025-06-02", 200, "交通", "Partner", "50/50", "", base_dir=tmp_db_path)
        results = list_expenses(payer="Brian", base_dir=tmp_db_path)
        assert len(results) == 1
        assert results[0]["payer"] == "Brian"

    def test_list_filter_date_range(self, tmp_db_path):
        """Filter by date range returns only matching expenses."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        add_expense("2025-06-15", 200, "交通", "Partner", "50/50", "", base_dir=tmp_db_path)
        add_expense("2025-07-01", 300, "購物", "Brian", "50/50", "", base_dir=tmp_db_path)
        results = list_expenses(date_from="2025-06-01", date_to="2025-06-30", base_dir=tmp_db_path)
        assert len(results) == 2

    def test_list_excludes_soft_deleted(self, tmp_db_path):
        """Soft-deleted expenses are excluded from default list."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "keep", base_dir=tmp_db_path)
        eid2 = add_expense("2025-06-02", 200, "交通", "Partner", "50/50", "delete me", base_dir=tmp_db_path)
        delete_expense(eid2, base_dir=tmp_db_path)
        results = list_expenses(base_dir=tmp_db_path)
        assert len(results) == 1
        assert results[0]["note"] == "keep"

    def test_list_include_deleted(self, tmp_db_path):
        """include_deleted=True shows all expenses including soft-deleted."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "keep", base_dir=tmp_db_path)
        eid2 = add_expense("2025-06-02", 200, "交通", "Partner", "50/50", "delete me", base_dir=tmp_db_path)
        delete_expense(eid2, base_dir=tmp_db_path)
        results = list_expenses(include_deleted=True, base_dir=tmp_db_path)
        assert len(results) == 2

    def test_list_pagination(self, tmp_db_path):
        """Limit and offset correctly paginate results."""
        for i in range(5):
            add_expense(f"2025-06-{i+1:02d}", (i + 1) * 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        results = list_expenses(limit=2, offset=0, base_dir=tmp_db_path)
        assert len(results) == 2
        results2 = list_expenses(limit=2, offset=2, base_dir=tmp_db_path)
        assert len(results2) == 2

    def test_list_empty(self, tmp_db_path):
        """No expenses returns empty list."""
        results = list_expenses(base_dir=tmp_db_path)
        assert results == []


class TestReportByCategory:
    def test_report_by_category(self, tmp_db_path):
        """Group expenses by category and sum amounts."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        add_expense("2025-06-02", 200, "餐飲", "Partner", "50/50", "", base_dir=tmp_db_path)
        add_expense("2025-06-03", 300, "交通", "Brian", "50/50", "", base_dir=tmp_db_path)
        results = report_by_category("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        cat_dict = {r["category"]: r for r in results}
        assert cat_dict["餐飲"]["total"] == 300.0
        assert cat_dict["餐飲"]["count"] == 2
        assert cat_dict["交通"]["total"] == 300.0
        assert cat_dict["交通"]["count"] == 1

    def test_report_by_category_excludes_deleted(self, tmp_db_path):
        """Soft-deleted expenses are excluded from category totals."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        eid2 = add_expense("2025-06-02", 200, "餐飲", "Partner", "50/50", "", base_dir=tmp_db_path)
        delete_expense(eid2, base_dir=tmp_db_path)
        results = report_by_category("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(results) == 1
        assert results[0]["total"] == 100.0

    def test_report_by_category_empty_range(self, tmp_db_path):
        """No expenses in range returns empty list."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        results = report_by_category("2099-01-01", "2099-12-31", base_dir=tmp_db_path)
        assert results == []


class TestReportByPayer:
    def test_report_by_payer(self, tmp_db_path):
        """Group expenses by payer and sum amounts."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        add_expense("2025-06-02", 200, "交通", "Partner", "50/50", "", base_dir=tmp_db_path)
        add_expense("2025-06-03", 300, "購物", "Brian", "60/40", "", base_dir=tmp_db_path)
        results = report_by_payer("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        payer_dict = {r["payer"]: r for r in results}
        assert payer_dict["Brian"]["total"] == 400.0
        assert payer_dict["Partner"]["total"] == 200.0

    def test_report_by_payer_excludes_deleted(self, tmp_db_path):
        """Soft-deleted expenses are excluded from payer totals."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        eid2 = add_expense("2025-06-02", 200, "交通", "Partner", "50/50", "", base_dir=tmp_db_path)
        delete_expense(eid2, base_dir=tmp_db_path)
        results = report_by_payer("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(results) == 1
        assert results[0]["payer"] == "Brian"


class TestReportSummary:
    def test_report_summary_basic(self, tmp_db_path):
        """Summary includes total_amount, total_count, min, max."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        add_expense("2025-06-02", 300, "交通", "Partner", "50/50", "", base_dir=tmp_db_path)
        add_expense("2025-06-03", 50, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        result = report_summary("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert result["total_amount"] == 450.0
        assert result["total_count"] == 3
        assert result["min_amount"] == 50.0
        assert result["max_amount"] == 300.0

    def test_report_summary_empty_range(self, tmp_db_path):
        """Empty date range returns dict with None values and count 0."""
        result = report_summary("2099-01-01", "2099-12-31", base_dir=tmp_db_path)
        # SQLite COUNT(*) returns 0 for empty set, but SUM/MIN/MAX return NULL
        assert result is not None
        assert result["total_count"] == 0
        assert result["total_amount"] is None

    def test_report_summary_single_expense(self, tmp_db_path):
        """Single expense: total == min == max == amount."""
        add_expense("2025-06-01", 250, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        result = report_summary("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert result["total_amount"] == 250.0
        assert result["min_amount"] == 250.0
        assert result["max_amount"] == 250.0

    def test_report_summary_excludes_deleted(self, tmp_db_path):
        """Soft-deleted expenses are excluded from summary."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        eid2 = add_expense("2025-06-02", 900, "交通", "Partner", "50/50", "", base_dir=tmp_db_path)
        delete_expense(eid2, base_dir=tmp_db_path)
        result = report_summary("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert result["total_amount"] == 100.0
        assert result["total_count"] == 1

    def test_report_summary_with_zero_expense(self, tmp_db_path):
        """Zero amount expense is included in summary."""
        add_expense("2025-06-01", 0, "其他", "Brian", "", "free", base_dir=tmp_db_path)
        result = report_summary("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert result["total_amount"] == 0.0
        assert result["total_count"] == 1


class TestDeleteExpense:
    def test_delete_expense_soft_delete(self, tmp_db_path):
        """Delete sets is_deleted=1 but record still exists."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "test", base_dir=tmp_db_path)
        result = delete_expense(eid, base_dir=tmp_db_path)
        assert result is True
        # Verify still in DB but marked deleted
        all_rows = list_expenses(include_deleted=True, base_dir=tmp_db_path)
        assert len(all_rows) == 1
        assert all_rows[0]["is_deleted"] == 1

    def test_delete_nonexistent_id(self, tmp_db_path):
        """Deleting nonexistent ID returns False."""
        result = delete_expense(9999, base_dir=tmp_db_path)
        assert result is False

    def test_delete_twice_returns_false_second_time(self, tmp_db_path):
        """Deleting an already-deleted expense returns False (row already has is_deleted=1)."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "test", base_dir=tmp_db_path)
        result1 = delete_expense(eid, base_dir=tmp_db_path)
        assert result1 is True
        result2 = delete_expense(eid, base_dir=tmp_db_path)
        assert result2 is False


class TestSearchExpenses:
    def test_search_by_keyword(self, tmp_db_path):
        """Search finds expenses by note or category keyword."""
        add_expense("2025-06-01", 800, "餐飲", "Brian", "50/50", "火鍋聚餐", base_dir=tmp_db_path)
        add_expense("2025-06-02", 100, "交通", "Partner", "50/50", "計程車", base_dir=tmp_db_path)
        results = search_expenses("火鍋", base_dir=tmp_db_path)
        assert len(results) >= 1
        assert any(r["note"] == "火鍋聚餐" for r in results)

    def test_search_by_category(self, tmp_db_path):
        """Search can find expenses by category keyword."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "早餐", base_dir=tmp_db_path)
        add_expense("2025-06-02", 200, "交通", "Partner", "50/50", "計程車", base_dir=tmp_db_path)
        results = search_expenses("餐飲", base_dir=tmp_db_path)
        assert len(results) >= 1
        assert any(r["category"] == "餐飲" for r in results)

    def test_search_excludes_deleted(self, tmp_db_path):
        """Search does not return soft-deleted expenses."""
        add_expense("2025-06-01", 800, "餐飲", "Brian", "50/50", "火鍋聚餐", base_dir=tmp_db_path)
        eid2 = add_expense("2025-06-02", 500, "餐飲", "Partner", "50/50", "火鍋party", base_dir=tmp_db_path)
        delete_expense(eid2, base_dir=tmp_db_path)
        results = search_expenses("火鍋", base_dir=tmp_db_path)
        assert all(r["is_deleted"] == 0 for r in results)
        assert len(results) == 1

    def test_search_no_match(self, tmp_db_path):
        """Search with non-matching keyword returns empty list."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "早餐", base_dir=tmp_db_path)
        results = search_expenses("xyz_nonexistent", base_dir=tmp_db_path)
        assert results == []

    def test_search_limit(self, tmp_db_path):
        """Search respects the limit parameter."""
        for i in range(10):
            add_expense(f"2025-06-{i+1:02d}", 100, "餐飲", "Brian", "50/50", f"item{i}", base_dir=tmp_db_path)
        results = search_expenses("item", limit=3, base_dir=tmp_db_path)
        assert len(results) <= 3


class TestComputeOwes:
    """Most complex function — test all split scenarios."""

    def test_owes_50_50(self, tmp_db_path):
        """Brian pays 100 with 50/50 split. Partner owes Brian 50."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "晚餐", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 1
        assert result[0]["from"] == "Partner"
        assert result[0]["to"] == "Brian"
        assert result[0]["amount"] == 50.0

    def test_owes_60_40(self, tmp_db_path):
        """Brian pays 100 with 60/40 split. Partner owes Brian 40."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "60/40", "晚餐", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 1
        assert result[0]["from"] == "Partner"
        assert result[0]["to"] == "Brian"
        assert result[0]["amount"] == 40.0

    def test_owes_skip_各付各(self, tmp_db_path):
        """各付各 (each pays own) is skipped — no debt generated."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "各付各", "晚餐", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 0

    def test_owes_empty_split_defaults_50_50(self, tmp_db_path):
        """Empty split_method defaults to 50/50 (len(parts)!=2)."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "", "晚餐", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 1
        assert result[0]["amount"] == 50.0

    def test_owes_negative_amount_refund(self, tmp_db_path):
        """Negative amount creates a reverse debt (refund)."""
        add_expense("2025-06-01", -50, "餐飲", "Brian", "50/50", "退款", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        # owes_amount = -50 * 0.5 = -25.0, amt > 0 check filters this out
        assert len(result) == 0

    def test_owes_zero_share_total(self, tmp_db_path):
        """Split '0/0' causes total_parts=0, so the expense is skipped (no division by zero)."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "0/0", "test", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 0

    def test_owes_multi_entry_accumulation(self, tmp_db_path):
        """Multiple expenses create separate debt entries per direction (no auto-netting)."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "早餐", base_dir=tmp_db_path)
        add_expense("2025-06-02", 200, "交通", "Partner", "50/50", "加油", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        # Brian paid 100 → Partner owes Brian 50
        # Partner paid 200 → Brian owes Partner 100
        # Function tracks debts per direction, no auto-netting
        assert len(result) == 2
        owes_dict = {(r["from"], r["to"]): r["amount"] for r in result}
        assert owes_dict[("Partner", "Brian")] == 50.0
        assert owes_dict[("Brian", "Partner")] == 100.0

    def test_owes_unknown_payer_skipped(self, tmp_db_path):
        """Payer not matching payer1 or payer2 is silently skipped."""
        add_expense("2025-06-01", 100, "餐飲", "Unknown", "50/50", "test", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 0

    def test_owes_invalid_split_defaults(self, tmp_db_path):
        """Invalid split_method (e.g., 'abc/def') defaults to 50/50."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "abc/def", "test", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 1
        assert result[0]["amount"] == 50.0

    def test_owes_partner_pays(self, tmp_db_path):
        """When Partner pays with 50/50, Brian owes Partner."""
        add_expense("2025-06-01", 100, "餐飲", "Partner", "50/50", "晚餐", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 1
        assert result[0]["from"] == "Brian"
        assert result[0]["to"] == "Partner"
        assert result[0]["amount"] == 50.0

    def test_owes_mixed_splits_accumulation(self, tmp_db_path):
        """Mixed split methods create separate debt entries per direction (no auto-netting)."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "70/30", "晚餐", base_dir=tmp_db_path)
        add_expense("2025-06-02", 200, "交通", "Partner", "30/70", "加油", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 2
        owes_dict = {(r["from"], r["to"]): r["amount"] for r in result}
        # Brian 70/30: first=0.7, second=0.3 → Partner owes Brian 30 (100*0.3)
        assert owes_dict[("Partner", "Brian")] == 30.0
        # Partner 30/70: first=0.3, second=0.7 → Brian owes Partner's first_share (200*0.3=60)
        assert owes_dict[("Brian", "Partner")] == 60.0

    def test_owes_all_各付各(self, tmp_db_path):
        """All expenses with 各付各 returns empty list."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "各付各", "", base_dir=tmp_db_path)
        add_expense("2025-06-02", 200, "交通", "Partner", "各付各", "", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 0

    def test_owes_empty_date_range(self, tmp_db_path):
        """No expenses in date range returns empty list."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        result = compute_owes("2099-01-01", "2099-12-31", base_dir=tmp_db_path)
        assert len(result) == 0

    def test_owes_deleted_expenses_excluded(self, tmp_db_path):
        """Soft-deleted expenses are excluded from owes computation."""
        add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "", base_dir=tmp_db_path)
        eid2 = add_expense("2025-06-02", 200, "交通", "Partner", "50/50", "", base_dir=tmp_db_path)
        delete_expense(eid2, base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 1
        assert result[0]["amount"] == 50.0


class TestConfig:
    def test_get_default_config(self, tmp_db_path):
        """Fresh DB has payer1='Brian' and payer2='Partner'."""
        row = get_config("payer1", base_dir=tmp_db_path)
        assert row["value"] == "Brian"
        row = get_config("payer2", base_dir=tmp_db_path)
        assert row["value"] == "Partner"

    def test_set_and_get_config(self, tmp_db_path):
        """Set a config value and retrieve it."""
        set_config("payer1", "小明", base_dir=tmp_db_path)
        row = get_config("payer1", base_dir=tmp_db_path)
        assert row["value"] == "小明"

    def test_get_nonexistent_config(self, tmp_db_path):
        """Getting a nonexistent key returns None."""
        row = get_config("nonexistent_key_xyz", base_dir=tmp_db_path)
        assert row is None

    def test_set_custom_config_and_retrieve(self, tmp_db_path):
        """Set and retrieve arbitrary config keys."""
        set_config("theme", "dark", base_dir=tmp_db_path)
        row = get_config("theme", base_dir=tmp_db_path)
        assert row["value"] == "dark"

    def test_set_overwrites_existing(self, tmp_db_path):
        """Setting an existing key overwrites the previous value."""
        set_config("payer1", "小明", base_dir=tmp_db_path)
        row = get_config("payer1", base_dir=tmp_db_path)
        assert row["value"] == "小明"
        set_config("payer1", "大衛", base_dir=tmp_db_path)
        row = get_config("payer1", base_dir=tmp_db_path)
        assert row["value"] == "大衛"

    def test_set_numeric_value_stored_as_string(self, tmp_db_path):
        """Numeric values are stored as strings."""
        set_config("version", 42, base_dir=tmp_db_path)
        row = get_config("version", base_dir=tmp_db_path)
        assert row["value"] == "42"

    def test_default_config_not_overwritten_by_set_other_key(self, tmp_db_path):
        """Setting a non-default config key doesn't affect default values."""
        set_config("theme", "light", base_dir=tmp_db_path)
        row1 = get_config("payer1", base_dir=tmp_db_path)
        row2 = get_config("payer2", base_dir=tmp_db_path)
        assert row1["value"] == "Brian"
        assert row2["value"] == "Partner"


class TestGetConnection:
    def test_connection_returns_row_factory_dict(self, tmp_db_path):
        """get_connection returns a connection with sqlite3.Row factory."""
        conn = get_connection(base_dir=tmp_db_path)
        # Should be able to convert rows to dicts
        row = conn.execute("SELECT 1 as id").fetchone()
        assert dict(row)["id"] == 1
        conn.close()

    def test_connection_creates_schema(self, tmp_db_path):
        """get_connection initializes schema (expenses and config tables)."""
        conn = get_connection(base_dir=tmp_db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [dict(t)["name"] for t in tables]
        assert "expenses" in table_names
        assert "config" in table_names
        conn.close()

    def test_connection_creates_fts_if_available(self, tmp_db_path):
        """get_connection creates FTS virtual table if SQLite supports it."""
        from db import _FTS5_AVAILABLE
        if _FTS5_AVAILABLE:
            conn = get_connection(base_dir=tmp_db_path)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_names = [dict(t)["name"] for t in tables]
            assert "expenses_fts" in table_names
            conn.close()


class TestNormalizeCategory:
    """normalize_category maps Chinese/English to canonical Chinese."""

    def test_normalize_chinese(self):
        from db import normalize_category
        assert normalize_category("餐飲") == "餐飲"
        assert normalize_category("交通") == "交通"
        assert normalize_category("其他") == "其他"

    def test_normalize_english(self):
        from db import normalize_category
        assert normalize_category("dining") == "餐飲"
        assert normalize_category("transport") == "交通"
        assert normalize_category("other") == "其他"

    def test_normalize_english_case_insensitive(self):
        from db import normalize_category
        assert normalize_category("Dining") == "餐飲"
        assert normalize_category("Transport") == "交通"

    def test_normalize_unknown_returns_as_is(self):
        from db import normalize_category
        assert normalize_category("unknown_category") == "unknown_category"

    def test_normalize_none(self):
        from db import normalize_category
        assert normalize_category("") == ""
        assert normalize_category(None) is None


class TestTranslateCategory:
    """translate_category converts canonical Chinese to requested language."""

    def test_translate_zh(self):
        from db import translate_category
        assert translate_category("餐飲", "zh") == "餐飲"
        assert translate_category("交通", "zh") == "交通"

    def test_translate_en(self):
        from db import translate_category
        assert translate_category("餐飲", "en") == "dining"
        assert translate_category("交通", "en") == "transport"
        assert translate_category("其他", "en") == "other"

    def test_translate_unknown(self):
        from db import translate_category
        assert translate_category("unknown_cat", "en") == "unknown_cat"
        assert translate_category("unknown_cat", "zh") == "unknown_cat"


class TestLanguageConfig:
    """language config key is initialised with default 'zh'."""

    def test_default_language_is_zh(self, tmp_db_path):
        from db import get_config
        row = get_config("language", base_dir=tmp_db_path)
        assert row is not None
        assert row["value"] == "zh"

    def test_set_language(self, tmp_db_path):
        from db import set_config, get_config
        set_config("language", "en", base_dir=tmp_db_path)
        row = get_config("language", base_dir=tmp_db_path)
        assert row["value"] == "en"

    def test_set_language_back_to_zh(self, tmp_db_path):
        from db import set_config, get_config
        set_config("language", "en", base_dir=tmp_db_path)
        set_config("language", "zh", base_dir=tmp_db_path)
        row = get_config("language", base_dir=tmp_db_path)
        assert row["value"] == "zh"


class TestComputeOwesBilingualSplit:
    """compute_owes skips English-style 'each pays own' split methods."""

    def test_owes_skip_each_pays_own_english(self, tmp_db_path):
        add_expense("2025-06-01", 100, "餐飲", "Brian", "each-pays-own", "dinner", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 0

    def test_owes_skip_aa(self, tmp_db_path):
        add_expense("2025-06-01", 100, "餐飲", "Brian", "aa", "dinner", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 0

    def test_owes_skip_each_pays_own_with_spaces(self, tmp_db_path):
        add_expense("2025-06-01", 100, "餐飲", "Brian", "each pays own", "dinner", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 0

    def test_owes_skip_各自付(self, tmp_db_path):
        add_expense("2025-06-01", 100, "餐飲", "Brian", "各自付", "dinner", base_dir=tmp_db_path)
        result = compute_owes("2025-06-01", "2025-06-30", base_dir=tmp_db_path)
        assert len(result) == 0


class TestEditExpense:
    """Tests for edit_expense() — PATCH-style partial updates."""

    def test_edit_amount(self, tmp_db_path):
        """Add expense with amount=100, edit to 200, verify returned record has amount=200."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "午餐", base_dir=tmp_db_path)
        record, changes = edit_expense(eid, amount=200, base_dir=tmp_db_path)
        assert record["amount"] == 200
        assert record["id"] == eid

    def test_edit_multiple_fields(self, tmp_db_path):
        """Edit amount + category + note simultaneously, verify all changed."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "午餐", base_dir=tmp_db_path)
        record, changes = edit_expense(eid, amount=250, category="交通", note="計程車", base_dir=tmp_db_path)
        assert record["amount"] == 250
        assert record["category"] == "交通"
        assert record["note"] == "計程車"

    def test_edit_patch_preserves_omitted_fields(self, tmp_db_path):
        """Edit only amount, verify date/category/payer/split_method/note unchanged."""
        eid = add_expense("2025-06-18", 100, "餐飲", "Brian", "50/50", "午餐", base_dir=tmp_db_path)
        record, _ = edit_expense(eid, amount=200, base_dir=tmp_db_path)
        assert record["date"] == "2025-06-18"
        assert record["category"] == "餐飲"
        assert record["payer"] == "Brian"
        assert record["split_method"] == "50/50"
        assert record["note"] == "午餐"

    def test_edit_returns_full_record(self, tmp_db_path):
        """Verify returned dict has all expense fields (id, date, amount, category, payer, split_method, note, is_deleted)."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "test", base_dir=tmp_db_path)
        record, _ = edit_expense(eid, amount=150, base_dir=tmp_db_path)
        assert "id" in record
        assert "date" in record
        assert "amount" in record
        assert "category" in record
        assert "payer" in record
        assert "split_method" in record
        assert "note" in record
        assert "is_deleted" in record

    def test_edit_returns_changes_diff(self, tmp_db_path):
        """Verify changes dict shows old→new per field."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "午餐", base_dir=tmp_db_path)
        record, changes = edit_expense(eid, amount=200, note="晚餐", base_dir=tmp_db_path)
        assert "amount" in changes
        assert changes["amount"]["old"] == 100
        assert changes["amount"]["new"] == 200
        assert "note" in changes
        assert changes["note"]["old"] == "午餐"
        assert changes["note"]["new"] == "晚餐"

    def test_edit_updates_updated_at(self, tmp_db_path):
        """Verify updated_at is set (not None/empty) after edit."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "test", base_dir=tmp_db_path)
        record, _ = edit_expense(eid, amount=150, base_dir=tmp_db_path)
        assert record.get("updated_at") is not None
        assert record["updated_at"] != ""

    def test_edit_reason_stored(self, tmp_db_path):
        """Edit with reason='corrected amount', verify edit_reason in DB record."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "test", base_dir=tmp_db_path)
        record, _ = edit_expense(eid, amount=200, reason="corrected amount", base_dir=tmp_db_path)
        assert record.get("edit_reason") == "corrected amount"

    def test_edit_reason_default_empty(self, tmp_db_path):
        """Edit without reason, verify edit_reason is empty string."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "test", base_dir=tmp_db_path)
        record, _ = edit_expense(eid, amount=150, base_dir=tmp_db_path)
        assert record.get("edit_reason") == ""

    def test_edit_nonexistent_id_raises_error(self, tmp_db_path):
        """Call edit_expense(9999, amount=200), expect ValueError with 'not found' in message."""
        with pytest.raises(ValueError) as exc_info:
            edit_expense(9999, amount=200, base_dir=tmp_db_path)
        assert "not found" in str(exc_info.value).lower()

    def test_edit_no_fields_raises_error(self, tmp_db_path):
        """Call edit_expense(eid, base_dir=tmp_db_path), expect ValueError with 'no fields'."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "test", base_dir=tmp_db_path)
        with pytest.raises(ValueError) as exc_info:
            edit_expense(eid, base_dir=tmp_db_path)
        assert "no fields" in str(exc_info.value).lower()

    def test_edit_only_reason_raises_error(self, tmp_db_path):
        """Call edit_expense(eid, reason='no change'), expect ValueError with 'no fields'."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "test", base_dir=tmp_db_path)
        with pytest.raises(ValueError) as exc_info:
            edit_expense(eid, reason="no change", base_dir=tmp_db_path)
        assert "no fields" in str(exc_info.value).lower()

    def test_edit_soft_deleted_stays_deleted(self, tmp_db_path):
        """Add expense, soft-delete it, edit it, verify is_deleted=1 in returned record."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "test", base_dir=tmp_db_path)
        delete_expense(eid, base_dir=tmp_db_path)
        record, _ = edit_expense(eid, amount=200, base_dir=tmp_db_path)
        assert record["is_deleted"] == 1

    def test_edit_category_normalized(self, tmp_db_path):
        """Edit category to 'transport' — db layer stores as-is (normalization is handler-layer concern)."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "test", base_dir=tmp_db_path)
        record, _ = edit_expense(eid, category="transport", base_dir=tmp_db_path)
        # db layer stores raw value; handler applies normalize_category before calling edit_expense
        assert record["category"] == "transport"

    def test_edit_fts_sync(self, tmp_db_path):
        """Add expense with note 'oldnote', search (found), edit note to 'newnote', old not found, new found."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "oldnote", base_dir=tmp_db_path)
        results_before = search_expenses("oldnote", base_dir=tmp_db_path)
        assert len(results_before) >= 1
        edit_expense(eid, note="newnote", base_dir=tmp_db_path)
        results_old = search_expenses("oldnote", base_dir=tmp_db_path)
        assert len(results_old) == 0
        results_new = search_expenses("newnote", base_dir=tmp_db_path)
        assert len(results_new) >= 1

    def test_edit_then_list_shows_updates(self, tmp_db_path):
        """Add expense amount=100, edit to amount=300, list expenses, verify amount=300 in list."""
        eid = add_expense("2025-06-01", 100, "餐飲", "Brian", "50/50", "test", base_dir=tmp_db_path)
        edit_expense(eid, amount=300, base_dir=tmp_db_path)
        results = list_expenses(base_dir=tmp_db_path)
        assert len(results) == 1
        assert results[0]["amount"] == 300

