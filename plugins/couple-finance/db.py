import sqlite3
from pathlib import Path
from contextlib import closing

try:
    from hermes_constants import get_hermes_home
except Exception:
    import os

    def get_hermes_home():
        val = (os.environ.get("HERMES_HOME") or "").strip()
        return Path(val).resolve() if val else (Path.home() / ".hermes").resolve()


_FTS5_AVAILABLE = True

#: Bidirectional category map: Chinese ↔ English, plus lowercase English variants.
#: All values map to the canonical Chinese name used in DB storage.
CATEGORY_MAP = {
    "餐飲": "餐飲", "交通": "交通", "購物": "購物", "娛樂": "娛樂",
    "住房": "住房", "水電": "水電", "醫療": "醫療", "教育": "教育", "其他": "其他",
    "dining": "餐飲", "transport": "交通", "shopping": "購物", "entertainment": "娛樂",
    "housing": "住房", "utilities": "水電", "medical": "醫療", "education": "教育", "other": "其他",
}

#: Canonical Chinese → English display name, used for output translation.
CATEGORY_EN = {
    "餐飲": "dining", "交通": "transport", "購物": "shopping", "娛樂": "entertainment",
    "住房": "housing", "水電": "utilities", "醫療": "medical", "教育": "education", "其他": "other",
}

#: All recognized split-method values that mean "each pays own" (skip in owes).
SPLIT_EACH_PAYS_OWN = {"各付各", "each-pays-own", "each pays own", "各自付", "各自", "aa"}


def normalize_category(category):
    """Normalize a category value to its canonical Chinese form.

    Accepts both Chinese (``餐飲``) and English (``dining``) names.
    Returns the canonical Chinese value used for DB storage.
    Falls back to the original input if not recognised.
    """
    if not category:
        return category
    canonical = CATEGORY_MAP.get(category)
    if canonical:
        return canonical
    canonical = CATEGORY_MAP.get(category.lower())
    if canonical:
        return canonical
    return category


def translate_category(category, lang="zh"):
    """Return *category* in the requested language (``"zh"`` or ``"en"``).

    The input should be the canonical Chinese value stored in the DB.
    Unknown values are returned unchanged.
    """
    if lang == "en" and category in CATEGORY_EN:
        return CATEGORY_EN[category]
    return category


def get_db_path(base_dir=None):
    if base_dir:
        return Path(base_dir) / "couple-finance.db"
    return get_hermes_home() / "couple-finance.db"


def _init_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            payer TEXT NOT NULL DEFAULT '',
            split_method TEXT DEFAULT '',
            note TEXT DEFAULT '',
            is_deleted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_payer ON expenses(payer)")

    global _FTS5_AVAILABLE
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_check USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS _fts5_check")
    except Exception:
        _FTS5_AVAILABLE = False

    if _FTS5_AVAILABLE:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS expenses_fts USING fts5(
                note, category,
                content='expenses',
                content_rowid='id'
            )
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS expenses_ai AFTER INSERT ON expenses BEGIN
                INSERT INTO expenses_fts(rowid, note, category) VALUES (new.id, new.note, new.category);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS expenses_ad AFTER DELETE ON expenses BEGIN
                INSERT INTO expenses_fts(expenses_fts, rowid, note, category) VALUES('delete', old.id, old.note, old.category);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS expenses_au AFTER UPDATE ON expenses BEGIN
                INSERT INTO expenses_fts(expenses_fts, rowid, note, category) VALUES('delete', old.id, old.note, old.category);
                INSERT INTO expenses_fts(rowid, note, category) VALUES (new.id, new.note, new.category);
            END
        """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('payer1', 'Brian')")
    conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('payer2', 'Partner')")
    conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('language', 'zh')")


def get_connection(base_dir=None):
    db_path = get_db_path(base_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _init_schema(conn)
    return conn


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def _rows_to_dicts(rows):
    return [dict(r) for r in rows]


def add_expense(date, amount, category, payer, split_method, note, base_dir=None):
    with closing(get_connection(base_dir)) as conn:
        cur = conn.execute(
            "INSERT INTO expenses (date, amount, category, payer, split_method, note) VALUES (?, ?, ?, ?, ?, ?)",
            (date, amount, category, payer, split_method, note),
        )
        conn.commit()
        return cur.lastrowid


def list_expenses(date_from=None, date_to=None, category=None, payer=None, limit=50, offset=0, include_deleted=False, base_dir=None):
    conditions = []
    params = []

    if not include_deleted:
        conditions.append("is_deleted = 0")

    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if payer:
        conditions.append("payer = ?")
        params.append(payer)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    with closing(get_connection(base_dir)) as conn:
        rows = conn.execute(
            f"SELECT * FROM expenses {where} ORDER BY date DESC, id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return _rows_to_dicts(rows)


def report_by_category(date_from, date_to, base_dir=None):
    with closing(get_connection(base_dir)) as conn:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total, COUNT(*) AS count FROM expenses WHERE is_deleted=0 AND date >= ? AND date <= ? GROUP BY category",
            (date_from, date_to),
        ).fetchall()
        return _rows_to_dicts(rows)


def report_by_payer(date_from, date_to, base_dir=None):
    with closing(get_connection(base_dir)) as conn:
        rows = conn.execute(
            "SELECT payer, SUM(amount) AS total, COUNT(*) AS count FROM expenses WHERE is_deleted=0 AND date >= ? AND date <= ? GROUP BY payer",
            (date_from, date_to),
        ).fetchall()
        return _rows_to_dicts(rows)


def report_summary(date_from, date_to, base_dir=None):
    with closing(get_connection(base_dir)) as conn:
        row = conn.execute(
            "SELECT SUM(amount) AS total_amount, COUNT(*) AS total_count, MIN(amount) AS min_amount, MAX(amount) AS max_amount FROM expenses WHERE is_deleted=0 AND date >= ? AND date <= ?",
            (date_from, date_to),
        ).fetchone()
        return _row_to_dict(row)


def delete_expense(expense_id, base_dir=None):
    with closing(get_connection(base_dir)) as conn:
        cur = conn.execute("UPDATE expenses SET is_deleted=1 WHERE id=? AND is_deleted=0", (expense_id,))
        conn.commit()
        return cur.rowcount > 0


def search_expenses(keyword, limit=20, base_dir=None):
    with closing(get_connection(base_dir)) as conn:
        rows = []
        if _FTS5_AVAILABLE:
            rows = conn.execute(
                "SELECT e.* FROM expenses e JOIN expenses_fts f ON e.id=f.rowid WHERE expenses_fts MATCH ? AND e.is_deleted=0 ORDER BY e.date DESC LIMIT ?",
                (keyword, limit),
            ).fetchall()

        if not rows:
            pattern = "%" + keyword + "%"
            rows = conn.execute(
                "SELECT * FROM expenses WHERE (note LIKE ? OR category LIKE ?) AND is_deleted=0 ORDER BY date DESC LIMIT ?",
                (pattern, pattern, limit),
            ).fetchall()

    return _rows_to_dicts(rows)


def compute_owes(date_from, date_to, base_dir=None):
    with closing(get_connection(base_dir)) as conn:
        row1 = conn.execute("SELECT value FROM config WHERE key='payer1'").fetchone()
        payer1 = dict(row1)["value"] if row1 else "Brian"
        row2 = conn.execute("SELECT value FROM config WHERE key='payer2'").fetchone()
        payer2 = dict(row2)["value"] if row2 else "Partner"

        expenses = conn.execute(
            "SELECT * FROM expenses WHERE is_deleted=0 AND date >= ? AND date <= ?",
            (date_from, date_to),
        ).fetchall()

    debts = {}
    for exp in expenses:
        exp_dict = dict(exp)
        split_method = exp_dict.get("split_method", "") or ""
        if split_method in SPLIT_EACH_PAYS_OWN:
            continue

        amount = float(exp_dict["amount"])
        payer = exp_dict["payer"]

        parts = [p.strip() for p in split_method.split("/")]
        if len(parts) != 2:
            first_share = 0.5
            second_share = 0.5
        else:
            try:
                total_parts = float(parts[0]) + float(parts[1])
                if total_parts == 0:
                    continue
                first_share = float(parts[0]) / total_parts
                second_share = float(parts[1]) / total_parts
            except ValueError:
                first_share = 0.5
                second_share = 0.5

        if payer == payer1:
            owes_amount = amount * second_share
            key = (payer2, payer1)
        elif payer == payer2:
            owes_amount = amount * first_share
            key = (payer1, payer2)
        else:
            continue

        debts[key] = round(debts.get(key, 0.0) + owes_amount, 2)

    result = []
    for (from_p, to_p), amt in sorted(debts.items()):
        if amt > 0:
            result.append({"from": from_p, "to": to_p, "amount": amt})
    return result


def get_config(key, base_dir=None):
    with closing(get_connection(base_dir)) as conn:
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return _row_to_dict(row)


def set_config(key, value, base_dir=None):
    with closing(get_connection(base_dir)) as conn:
        conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
