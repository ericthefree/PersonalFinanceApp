from flask import Flask, render_template, request, redirect, url_for
import csv
from io import TextIOWrapper
from datetime import datetime
from decimal import Decimal, InvalidOperation
import sqlite3
from pathlib import Path

DB_PATH = Path("instance/transactions.db")

app = Flask(__name__)


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist and ensure extra columns exist."""
    conn = get_db_connection()
    cur = conn.cursor()

    # Base transactions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_key TEXT NOT NULL,
            date_raw TEXT NOT NULL,
            description TEXT NOT NULL,    -- original/bank description
            amount TEXT NOT NULL          -- stored as string, parsed as Decimal
        )
    """)

    # Ensure extra metadata columns exist
    cur.execute("PRAGMA table_info(transactions)")
    existing_cols = {row[1] for row in cur.fetchall()}

    extra_columns = [
        ("custom_description", "TEXT"),
        ("category_type", "TEXT"),
        ("parent_category", "TEXT"),
        ("sub_category", "TEXT"),
        ("is_recurring", "INTEGER")   # 0 or 1
    ]
    for col_name, col_type in extra_columns:
        if col_name not in existing_cols:
            cur.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}")

    # Settings table (for current balance)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_current_balance():
    """Read current balance from settings table, if present."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = 'current_balance'")
    row = cur.fetchone()
    conn.close()

    if not row or row["value"] is None:
        return None

    try:
        return Decimal(row["value"])
    except InvalidOperation:
        return None


def set_current_balance(value: Decimal):
    """Store current balance in settings table."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO settings (key, value)
        VALUES ('current_balance', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(value),),
    )
    conn.commit()
    conn.close()


def parse_date(date_str: str):
    """Try to parse the incoming date in common formats."""
    if not date_str:
        return None

    date_str = date_str.strip()

    formats = [
        "%Y-%m-%d",    # 2025-11-10
        "%m/%d/%Y",    # 11/10/2025
        "%m/%d/%y",    # 11/10/25
        "%d/%m/%Y",    # 10/11/2025
        "%d-%m-%Y",    # 10-11-2025
        "%d-%b-%y",    # 10-Nov-25
        "%d-%b-%Y",    # 10-Nov-2025
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def normalize_amount(value: Decimal) -> Decimal:
    """Normalize to 2 decimal places."""
    return value.quantize(Decimal("0.01"))


@app.template_filter("currency")
def currency_filter(value):
    """
    Format Decimal as US currency with 2 decimal places.
    Always show as positive (no negative sign).
    """
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = Decimal(value)
        except InvalidOperation:
            return value
    value = normalize_amount(value)
    return f"${abs(value):,.2f}"


def load_transactions():
    """Load all transactions newest-to-oldest."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date_key, date_raw, description, amount,
               custom_description, category_type, parent_category,
               sub_category, is_recurring
        FROM transactions
        ORDER BY date_key DESC, id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def build_transaction_view(rows, current_balance):
    """
    Build a list of transaction dicts with computed balance and
    display-friendly date/description.
    """
    transactions = []
    running_balance = current_balance

    for row in rows:
        amount = Decimal(row["amount"])

        # Date display
        date_display = None
        dk = row["date_key"]
        try:
            if dk and len(dk) == 10:
                d = datetime.strptime(dk, "%Y-%m-%d")
                date_display = d.strftime("%d-%b-%y")
        except ValueError:
            pass
        if not date_display:
            date_display = row["date_raw"]

        balance_for_row = running_balance if running_balance is not None else None

        transactions.append({
            "id": row["id"],
            "date_display": date_display,
            "description": row["description"],            # bank description
            "custom_description": row["custom_description"],
            "display_description": row["custom_description"] or row["description"],
            "amount": amount,
            "balance": balance_for_row,
            "category_type": row["category_type"],
            "parent_category": row["parent_category"],
            "sub_category": row["sub_category"],
            "is_recurring": bool(row["is_recurring"]) if row["is_recurring"] is not None else False,
        })

        if running_balance is not None:
            running_balance -= amount

    return transactions


@app.route("/", methods=["GET"])
def index():
    """Summary page: read-only view of transactions."""
    current_balance = get_current_balance()
    rows = load_transactions()
    transactions = build_transaction_view(rows, current_balance)

    return render_template(
        "index.html",
        transactions=transactions,
        current_balance=current_balance,
        active_tab="summary",
    )


@app.route("/manage", methods=["GET", "POST"])
def manage():
    """
    Management page:
      - set current balance
      - upload CSV
      - add manual transaction
      - edit custom desc / category / recurring
      - delete transactions
    """
    error = None
    duplicates = []
    current_balance = get_current_balance()

    if request.method == "POST":
        action = request.form.get("action")

        # UPDATE CURRENT BALANCE
        if action == "set_balance":
            raw = (request.form.get("current_balance") or "").replace(",", "").strip()
            if not raw:
                error = "Current balance is required."
            else:
                try:
                    cb = Decimal(raw)
                    cb = normalize_amount(cb)
                    set_current_balance(cb)
                    current_balance = cb
                except InvalidOperation:
                    error = "Current balance must be a valid number."

        # UPLOAD / APPEND CSV
        elif action == "upload":
            uploaded_file = request.files.get("file")
            if uploaded_file and uploaded_file.filename:
                conn = get_db_connection()
                cur = conn.cursor()

                wrapper = TextIOWrapper(uploaded_file.stream, encoding="utf-8-sig")
                reader = csv.DictReader(wrapper)

                seen_duplicate_ids = set()

                for row in reader:
                    date_str = row.get("date") or row.get("Date") or row.get("DATE")
                    desc = row.get("description") or row.get("Description") or row.get("DESCRIPTION")
                    amt_str = row.get("amount") or row.get("Amount") or row.get("AMOUNT")

                    if not (date_str and desc and amt_str):
                        continue

                    date_str = date_str.strip()
                    desc = desc.strip()

                    date_obj = parse_date(date_str)

                    try:
                        amount = Decimal(amt_str.replace(",", "").strip())
                    except InvalidOperation:
                        continue

                    amount = normalize_amount(amount)
                    amount_str = str(amount)

                    if date_obj:
                        date_key = date_obj.date().isoformat()  # YYYY-MM-DD
                        date_raw = date_str
                    else:
                        date_key = date_str
                        date_raw = date_str

                    # detect duplicates
                    cur.execute(
                        """
                        SELECT id, date_key, date_raw, description, amount
                        FROM transactions
                        WHERE date_key = ? AND description = ? AND amount = ?
                        """,
                        (date_key, desc, amount_str),
                    )
                    existing_rows = cur.fetchall()

                    if existing_rows:
                        for existing in existing_rows:
                            existing_id = existing["id"]
                            if existing_id not in seen_duplicate_ids:
                                seen_duplicate_ids.add(existing_id)

                                duplicate_date_display = None
                                try:
                                    dk = existing["date_key"]
                                    if dk and len(dk) == 10:
                                        d = datetime.strptime(dk, "%Y-%m-%d")
                                        duplicate_date_display = d.strftime("%d-%b-%y")
                                except ValueError:
                                    pass
                                if not duplicate_date_display:
                                    duplicate_date_display = existing["date_raw"]

                                duplicates.append({
                                    "id": existing_id,
                                    "date_display": duplicate_date_display,
                                    "description": existing["description"],
                                    "amount": Decimal(existing["amount"]),
                                })
                    else:
                        # insert
                        cur.execute(
                            """
                            INSERT INTO transactions
                            (date_key, date_raw, description, amount, is_recurring)
                            VALUES (?, ?, ?, ?, 0)
                            """,
                            (date_key, date_raw, desc, amount_str),
                        )

                conn.commit()
                conn.close()

        # DELETE SELECTED DUPLICATE IDS
        elif action == "delete_duplicates":
            delete_ids = request.form.getlist("delete_ids")
            if delete_ids:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.executemany("DELETE FROM transactions WHERE id = ?", [(i,) for i in delete_ids])
                conn.commit()
                conn.close()

        # DELETE A SINGLE TRANSACTION
        elif action == "delete_tx":
            tx_id = request.form.get("tx_id")
            if tx_id:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
                conn.commit()
                conn.close()

        # UPDATE METADATA (custom desc / category / recurring)
        elif action == "update_tx_meta":
            tx_id = request.form.get("tx_id")
            if tx_id:
                custom_description = (request.form.get("custom_description") or "").strip() or None
                category_type = (request.form.get("category_type") or "").strip() or None
                parent_category = (request.form.get("parent_category") or "").strip() or None
                sub_category = (request.form.get("sub_category") or "").strip() or None
                is_recurring_raw = request.form.get("is_recurring")
                is_recurring = 1 if is_recurring_raw == "1" else 0

                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE transactions
                    SET custom_description = ?,
                        category_type = ?,
                        parent_category = ?,
                        sub_category = ?,
                        is_recurring = ?
                    WHERE id = ?
                    """,
                    (custom_description, category_type, parent_category,
                     sub_category, is_recurring, tx_id),
                )
                conn.commit()
                conn.close()

        # ADD A NEW MANUAL TRANSACTION
        elif action == "add_tx":
            date_str = (request.form.get("new_date") or "").strip()
            desc = (request.form.get("new_description") or "").strip()
            amt_str = (request.form.get("new_amount") or "").replace(",", "").strip()

            custom_description = (request.form.get("new_custom_description") or "").strip() or None
            category_type = (request.form.get("new_category_type") or "").strip() or None
            parent_category = (request.form.get("new_parent_category") or "").strip() or None
            sub_category = (request.form.get("new_sub_category") or "").strip() or None
            is_recurring_raw = request.form.get("new_is_recurring")
            is_recurring = 1 if is_recurring_raw == "1" else 0

            if not (date_str and desc and amt_str):
                error = "Date, description, and amount are required for a new transaction."
            else:
                date_obj = parse_date(date_str)
                try:
                    amount = Decimal(amt_str)
                except InvalidOperation:
                    error = "Amount must be a valid number."

                if not error:
                    amount = normalize_amount(amount)
                    if date_obj:
                        date_key = date_obj.date().isoformat()
                        date_raw = date_str
                    else:
                        date_key = date_str
                        date_raw = date_str

                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute(
                        """
                        INSERT INTO transactions
                        (date_key, date_raw, description, amount,
                         custom_description, category_type,
                         parent_category, sub_category, is_recurring)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (date_key, date_raw, desc, str(amount),
                         custom_description, category_type,
                         parent_category, sub_category, is_recurring),
                    )
                    conn.commit()
                    conn.close()

        # refresh balance after any action that might change it
        current_balance = get_current_balance()

        # optional: avoid resubmission if you reload page
        # return redirect(url_for("manage"))

    rows = load_transactions()
    transactions = build_transaction_view(rows, current_balance)

    return render_template(
        "manage.html",
        transactions=transactions,
        current_balance=current_balance,
        error=error,
        duplicates=duplicates,
        active_tab="manage",
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001, debug=True)
