"""Couple Finance plugin — expense tracking with SQLite storage."""
import json
from datetime import date

try:
    from .db import (
        add_expense, list_expenses, report_by_category, report_by_payer,
        report_summary, delete_expense, search_expenses, compute_owes,
        get_config, set_config, normalize_category, translate_category,
        edit_expense,
    )
except ImportError:
    # pytest discovers hyphenated dirs as test modules; use absolute imports
    from db import (
        add_expense, list_expenses, report_by_category, report_by_payer,
        report_summary, delete_expense, search_expenses, compute_owes,
        get_config, set_config, normalize_category, translate_category,
        edit_expense,
    )

# --- Tool Schemas ---

EXPENSE_ADD_SCHEMA = {
    "name": "expense_add",
    "description": "Record an expense entry. Use this when the user reports a payment or expense. Extract the amount, category, payer, split method, and note from their natural language input. If no date mentioned, use today. If no payer mentioned, ask or use default.",
    "parameters": {
        "type": "object",
        "properties": {
            "amount": {"type": "number", "description": "Expense amount (required)"},
            "category": {"type": "string", "enum": ["餐飲", "交通", "購物", "娛樂", "住房", "水電", "醫療", "教育", "其他", "dining", "transport", "shopping", "entertainment", "housing", "utilities", "medical", "education", "other"], "description": "Expense category — accepts Chinese (e.g. 餐飲) or English (e.g. dining). Infer from context."},
            "date": {"type": "string", "description": "Date in YYYY-MM-DD format. Default to today if not specified."},
            "payer": {"type": "string", "description": "Who paid (e.g. Brian, Partner, 共同)"},
            "split_method": {"type": "string", "description": "How to split: 50/50, 60/40, 各付各 / each-pays-own. Defaults to 50/50."},
            "note": {"type": "string", "description": "Free-text description of the expense"}
        },
        "required": ["amount"]
    }
}

EXPENSE_LIST_SCHEMA = {
    "name": "expense_list",
    "description": "List recorded expenses with optional filters. Returns a paginated list of expense entries.",
    "parameters": {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "Start date YYYY-MM-DD (inclusive)"},
            "date_to": {"type": "string", "description": "End date YYYY-MM-DD (inclusive)"},
            "category": {"type": "string", "enum": ["餐飲", "交通", "購物", "娛樂", "住房", "水電", "醫療", "教育", "其他", "dining", "transport", "shopping", "entertainment", "housing", "utilities", "medical", "education", "other"], "description": "Filter by category — accepts Chinese or English"},
            "payer": {"type": "string", "description": "Filter by payer (e.g. Brian, Partner, 共同)"},
            "limit": {"type": "integer", "description": "Max results (default 50, max 200)"},
            "offset": {"type": "integer", "description": "Skip N results for pagination"}
        },
        "required": []
    }
}

EXPENSE_REPORT_SCHEMA = {
    "name": "expense_report",
    "description": "Get aggregated expense report. Returns totals by category, by payer, an overall summary, and who-owes-whom calculation based on split methods.",
    "parameters": {
        "type": "object",
        "properties": {
            "date_from": {"type": "string", "description": "Start date YYYY-MM-DD (default: first of current month)"},
            "date_to": {"type": "string", "description": "End date YYYY-MM-DD (default: today)"}
        },
        "required": []
    }
}

EXPENSE_DELETE_SCHEMA = {
    "name": "expense_delete",
    "description": "Soft-delete an expense by its ID. The data is preserved in the database but excluded from all queries and reports.",
    "parameters": {
        "type": "object",
        "properties": {
            "expense_id": {"type": "integer", "description": "ID of the expense to delete"},
            "reason": {"type": "string", "description": "Optional reason for deletion"}
        },
        "required": ["expense_id"]
    }
}

EXPENSE_EDIT_SCHEMA = {
    "name": "expense_edit",
    "description": "Edit an existing expense. PATCH-style partial update — only provided fields are changed. Returns the full updated record plus a diff of what changed.",
    "parameters": {
        "type": "object",
        "properties": {
            "expense_id": {"type": "integer", "description": "ID of the expense to edit"},
            "amount": {"type": "number", "description": "New amount"},
            "category": {"type": "string", "enum": ["餐飲", "交通", "購物", "娛樂", "住房", "水電", "醫療", "教育", "其他", "dining", "transport", "shopping", "entertainment", "housing", "utilities", "medical", "education", "other"], "description": "New category — accepts Chinese (e.g. 餐飲) or English (e.g. dining)."},
            "date": {"type": "string", "description": "New date in YYYY-MM-DD format"},
            "payer": {"type": "string", "description": "New payer"},
            "split_method": {"type": "string", "description": "New split method"},
            "note": {"type": "string", "description": "New note text"},
            "reason": {"type": "string", "description": "Reason for editing"}
        },
        "required": ["expense_id"]
    }
}

EXPENSE_SEARCH_SCHEMA = {
    "name": "expense_search",
    "description": "Search expenses by keyword. Uses FTS5 full-text search if available, otherwise falls back to LIKE pattern matching. Returns matching expenses sorted by date.",
    "parameters": {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "Search keyword (FTS5 MATCH query)"},
            "limit": {"type": "integer", "description": "Max results (default 20)"}
        },
        "required": ["keyword"]
    }
}

EXPENSE_CONFIG_SCHEMA = {
    "name": "expense_config",
    "description": "Get or set configuration for the couple-finance plugin. Use to customize payer names or other settings.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["get", "set"], "description": "'get' to read config, 'set' to write"},
            "key": {"type": "string", "description": "Config key (e.g. 'payer1', 'payer2')"},
            "value": {"type": "string", "description": "Value to set (required if action='set')"}
        },
        "required": ["action", "key"]
    }
}

# --- Handlers ---


def _handle_expense_add(args: dict, **kw) -> str:
    try:
        amount = args["amount"]
        category = normalize_category(args.get("category", "其他"))
        expense_date = args.get("date", date.today().isoformat())
        payer = args.get("payer", "")
        split_method = args.get("split_method", "50/50")
        note = args.get("note", "")
        base_dir = args.get("base_dir")

        eid = add_expense(expense_date, amount, category, payer, split_method, note, base_dir=base_dir)
        return json.dumps({"ok": True, "id": eid}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _handle_expense_list(args: dict, **kw) -> str:
    try:
        base_dir = args.get("base_dir")
        raw_category = args.get("category")
        category = normalize_category(raw_category) if raw_category else None
        expenses = list_expenses(
            date_from=args.get("date_from"),
            date_to=args.get("date_to"),
            category=category,
            payer=args.get("payer"),
            limit=args.get("limit", 50),
            offset=args.get("offset", 0),
            base_dir=base_dir,
        )
        return json.dumps({"ok": True, "expenses": expenses}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _handle_expense_report(args: dict, **kw) -> str:
    try:
        today = date.today()
        date_from = args.get("date_from", today.replace(day=1).isoformat())
        date_to = args.get("date_to", today.isoformat())
        base_dir = args.get("base_dir")

        by_category = report_by_category(date_from, date_to, base_dir=base_dir)
        by_payer = report_by_payer(date_from, date_to, base_dir=base_dir)
        summary = report_summary(date_from, date_to, base_dir=base_dir) or {}
        owes = compute_owes(date_from, date_to, base_dir=base_dir)

        config_row = get_config("language", base_dir=base_dir)
        lang = (config_row or {}).get("value", "zh")

        if lang == "en":
            for item in by_category:
                item["category"] = translate_category(item.get("category", ""), lang)

        return json.dumps({
            "ok": True,
            "by_category": by_category,
            "by_payer": by_payer,
            "summary": summary,
            "owes": owes,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _handle_expense_delete(args: dict, **kw) -> str:
    try:
        expense_id = args["expense_id"]
        base_dir = args.get("base_dir")
        deleted = delete_expense(expense_id, base_dir=base_dir)
        return json.dumps({"ok": True, "id": expense_id, "deleted": deleted}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _handle_expense_edit(args: dict, **kw) -> str:
    try:
        expense_id = args["expense_id"]
        base_dir = args.get("base_dir")

        # Build kwargs with only editable fields that were provided
        editable = ["amount", "category", "date", "payer", "split_method", "note"]
        kwargs = {}
        for field in editable:
            if field in args:
                kwargs[field] = args[field]

        # Normalize category if provided
        if "category" in kwargs:
            kwargs["category"] = normalize_category(kwargs["category"])

        # Add reason if provided
        if "reason" in args:
            kwargs["reason"] = args["reason"]

        record, changes = edit_expense(expense_id, base_dir=base_dir, **kwargs)
        return json.dumps({"ok": True, "id": expense_id, "expense": record, "diff": changes}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _handle_expense_search(args: dict, **kw) -> str:
    try:
        keyword = args["keyword"]
        limit = args.get("limit", 20)
        base_dir = args.get("base_dir")
        results = search_expenses(keyword, limit, base_dir=base_dir)
        return json.dumps({"ok": True, "results": results}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _handle_expense_config(args: dict, **kw) -> str:
    try:
        action = args["action"]
        key = args["key"]
        base_dir = args.get("base_dir")

        if action == "get":
            row = get_config(key, base_dir=base_dir)
            return json.dumps({"ok": True, "key": key, "value": row.get("value") if row else None}, ensure_ascii=False)
        elif action == "set":
            value = args.get("value", "")
            set_config(key, value, base_dir=base_dir)
            return json.dumps({"ok": True, "key": key, "value": str(value), "updated": True}, ensure_ascii=False)
        else:
            return json.dumps({"error": f"Unknown action: {action}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# --- Registration ---

def register(ctx):
    ctx.register_tool(name="expense_add", toolset="couple-finance", schema=EXPENSE_ADD_SCHEMA, handler=_handle_expense_add)
    ctx.register_tool(name="expense_list", toolset="couple-finance", schema=EXPENSE_LIST_SCHEMA, handler=_handle_expense_list)
    ctx.register_tool(name="expense_report", toolset="couple-finance", schema=EXPENSE_REPORT_SCHEMA, handler=_handle_expense_report)
    ctx.register_tool(name="expense_delete", toolset="couple-finance", schema=EXPENSE_DELETE_SCHEMA, handler=_handle_expense_delete)
    ctx.register_tool(name="expense_edit", toolset="couple-finance", schema=EXPENSE_EDIT_SCHEMA, handler=_handle_expense_edit)
    ctx.register_tool(name="expense_search", toolset="couple-finance", schema=EXPENSE_SEARCH_SCHEMA, handler=_handle_expense_search)
    ctx.register_tool(name="expense_config", toolset="couple-finance", schema=EXPENSE_CONFIG_SCHEMA, handler=_handle_expense_config)
