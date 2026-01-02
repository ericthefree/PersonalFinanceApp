from flask import Flask, render_template, request, redirect, url_for, send_file
import io

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
            description TEXT NOT NULL,
            amount REAL NOT NULL
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
        ("is_recurring", "INTEGER")
    ]

    for col_name, col_type in extra_columns:
        if col_name not in existing_cols:
            cur.execute(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}")

    # Settings table (for current balance) - CREATE THIS FIRST
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # NOW check and initialize values
    cur.execute("SELECT value FROM settings WHERE key = 'current_balance'")
    if cur.fetchone() is None:
        cur.execute("INSERT INTO settings (key, value) VALUES ('current_balance', '0.0')")

    # Initialize starting_balance if it doesn't exist
    cur.execute("SELECT value FROM settings WHERE key = 'starting_balance'")
    if cur.fetchone() is None:
        cur.execute("INSERT INTO settings (key, value) VALUES ('starting_balance', '0.0')")

    # Create indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_date ON transactions(date_key)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_category ON transactions(category_type)")

    conn.commit()
    conn.close()


def get_recent_transactions_with_balance(limit=50):
    """Get recent transactions with running balance calculated in SQL"""
    query = """
        SELECT 
            *,
            (SELECT COALESCE(SUM(
                CASE 
                    WHEN category_type = 'income' THEN amount 
                    WHEN category_type = 'expense' THEN -amount 
                END
            ), 0)
            FROM transactions t2 
            WHERE t2.id <= t1.id) as running_balance
        FROM transactions t1
        ORDER BY date_key DESC, id DESC
        LIMIT ?
    """
    conn = get_db_connection()
    cur = conn.cursor()

    return cur.execute(query, (limit,)).fetchall()


def get_current_balance():
    """Read current balance from settings table, if present."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = 'current_balance'")
    row = cur.fetchone()
    conn.close()

    return Decimal(row["value"]) if row else Decimal("0.0")


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


def parse_date(date_str):
    """
    Parse various date formats. If year is missing, assume current year.
    Returns a datetime object or None.
    """
    if not date_str:
        return None

    current_year = datetime.now().year
    date_str = date_str.strip()

    # Common formats to try (with year)
    formats_with_year = [
        "%m/%d/%Y",  # 11/10/2025
        "%m-%d-%Y",  # 11-10-2025
        "%d-%b-%y",  # 10-Nov-25
        "%d-%b-%Y",  # 10-Nov-2025
        "%Y-%m-%d",  # 2025-11-10
        "%m/%d/%y",  # 11/10/25
        "%d/%m/%Y",  # 10/11/2025
        "%d/%m/%y",  # 10/11/25
    ]

    # Formats without year (will add current year)
    formats_without_year = [
        "%m/%d",  # 11/10
        "%m-%d",  # 11-10
        "%d-%b",  # 10-Nov
    ]

    # Try formats with year first
    for fmt in formats_with_year:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # Try formats without year, then add current year
    for fmt in formats_without_year:
        try:
            parsed = datetime.strptime(date_str, fmt)
            # Add current year
            return parsed.replace(year=current_year)
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


def load_transactions(page=1, per_page=50):
    """Load all transactions newest-to-oldest."""
    conn = get_db_connection()
    cur = conn.cursor()
    offset = (page - 1) * per_page

    # Get the paginated rows
    rows = cur.execute("""
                       SELECT id,
                              date_key,
                              date_raw,
                              description,
                              amount,
                              custom_description,
                              category_type,
                              parent_category,
                              sub_category,
                              is_recurring
                       FROM transactions
                       ORDER BY date_key DESC, id DESC
                       LIMIT ? OFFSET ?""",
                       (per_page, offset)).fetchall()

    # Get total count with a separate query
    cur.execute("SELECT COUNT(*) FROM transactions")
    total = cur.fetchone()[0]

    conn.close()

    return rows, total


def build_transaction_view(total, rows, current_balance):
    """
    Build a list of transaction dicts with computed balance and
    display-friendly date/description.
    """
    transactions = []
    running_balance = current_balance
    if total:
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
                "display_description": row["custom_description"] if row["custom_description"] else row["description"],
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
@app.route("/page/<int:page>", methods=["GET"])
def index(page=1):
    """Summary page: read-only view of transactions."""
    init_db()
    current_balance = get_current_balance()
    rows, total = load_transactions(page=page, per_page=100)
    transactions = build_transaction_view(total, rows, current_balance)

    per_page = 100
    total_pages = (total + per_page - 1) // per_page if total else 0

    return render_template(
        "index.html",
        transactions=transactions,
        current_balance=current_balance,
        active_tab="summary",
        page=page,
        total_pages=total_pages,
        total_transactions=total
    )


@app.route("/manage", methods=["GET", "POST"])
@app.route("/manage/<int:page>", methods=["GET", "POST"])
def manage(page=1):
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

    if request.method == "POST":
        action = request.form.get("action")

        conn = get_db_connection()
        cur = conn.cursor()

        # UPDATE CURRENT BALANCE
        # UPDATE CURRENT BALANCE
        if action == "set_balance":
            raw = (request.form.get("current_balance") or "").replace(",", "").strip()
            if not raw:
                print("Current balance is required.")
            else:
                try:
                    cb = Decimal(raw)
                    cb = normalize_amount(cb)  # Already doing this - good!

                    # Calculate what the starting balance must have been
                    # starting_balance = current_balance - sum(all transactions)
                    cur.execute("SELECT COALESCE(SUM(CAST(amount AS REAL)), 0) FROM transactions")
                    total_transactions = Decimal(str(cur.fetchone()[0]))
                    total_transactions = normalize_amount(total_transactions)  # NORMALIZE

                    starting_balance = cb - total_transactions
                    starting_balance = normalize_amount(starting_balance)  # NORMALIZE

                    # Store both values
                    set_current_balance(cb)
                    cur.execute("""
                        INSERT OR REPLACE INTO settings (key, value)
                        VALUES ('starting_balance', ?)
                    """, (str(starting_balance),))
                except InvalidOperation:
                    print("Current balance must be a valid number.")

        # UPLOAD / APPEND CSV
        elif action == "upload":
            uploaded_file = request.files.get("file")

            if uploaded_file and uploaded_file.filename:

                # Check database state
                cur.execute("SELECT COUNT(*) FROM transactions")
                count = cur.fetchone()[0]
                print(f"DATABASE STATUS: {count} transactions currently in database")

                if count > 0:
                    print("WARNING: Database is NOT empty. All matching transactions will be marked as duplicates.")

                # Get all existing transaction IDs BEFORE import starts
                cur.execute("SELECT id FROM transactions")
                pre_import_ids = {row["id"] for row in cur.fetchall()}

                print(f"DEBUG: Pre-import IDs: {pre_import_ids}")  # Should be empty set() if DB is empty

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
                        date_key = date_obj.date().isoformat()
                        date_raw = date_str
                    else:
                        date_key = date_str
                        date_raw = date_str

                    # detect duplicates
                    cur.execute(
                        """
                        SELECT id, date_key, date_raw, description, amount
                        FROM transactions
                        WHERE date_key = ?
                          AND description = ?
                          AND amount = ?
                        """,
                        (date_key, desc, amount_str),
                    )
                    existing_rows = cur.fetchall()

                    print(f"DEBUG: Found {len(existing_rows)} existing rows for {desc}")
                    print(f"DEBUG: Existing row IDs: {[r['id'] for r in existing_rows]}")

                    # Filter to only pre-import transactions
                    available_duplicates = [
                        row for row in existing_rows
                        if row["id"] in pre_import_ids and row["id"] not in seen_duplicate_ids
                    ]

                    print(f"DEBUG: Available duplicates after filter: {len(available_duplicates)}")

                    if available_duplicates:
                        existing = available_duplicates[0]
                        existing_id = existing["id"]
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
                        # No matches in pre-existing transactions - insert as new
                        print(f"INSERTING NEW: {desc[:50]}...")  # Add this line
                        cur.execute(
                            """
                            INSERT INTO transactions
                                (date_key, date_raw, description, amount, is_recurring)
                            VALUES (?, ?, ?, ?, 0)
                            """,
                            (date_key, date_raw, desc, amount_str),
                        )

        # DELETE SELECTED DUPLICATE IDS
        elif action == "delete_duplicates":
            delete_ids = request.form.getlist("delete_ids")
            if delete_ids:
                cur.executemany("DELETE FROM transactions WHERE id = ?", [(i,) for i in delete_ids])

        # DELETE A SINGLE TRANSACTION
        elif action == "delete_tx":
            tx_id = request.form.get("tx_id")

            if tx_id:
                cur.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))

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

        # UPDATE ALL TRANSACTIONS (from the big edit form)
        elif action == "save_all":
            row_ids = request.form.getlist("row_id")

            for row_id in row_ids:
                custom_description = (request.form.get(f"custom_description_{row_id}") or "").strip() or None
                category_type = (request.form.get(f"category_type_{row_id}") or "").strip() or None
                parent_category = (request.form.get(f"parent_category_{row_id}") or "").strip() or None
                sub_category = (request.form.get(f"sub_category_{row_id}") or "").strip() or None
                is_recurring = 1 if request.form.get(f"is_recurring_{row_id}") else 0

                # Get propagate_to list for this transaction
                propagate_to_str = request.form.get(f"propagate_to_{row_id}", "")
                propagate_ids = [x.strip() for x in propagate_to_str.split(",") if x.strip()]

                # Update the main transaction
                cur.execute(
                    """
                    UPDATE transactions
                    SET custom_description = ?,
                        category_type      = ?,
                        parent_category    = ?,
                        sub_category       = ?,
                        is_recurring       = ?
                    WHERE id = ?
                    """,
                    (custom_description, category_type, parent_category,
                     sub_category, is_recurring, row_id),
                )

                # Also update any similar transactions if propagate_to is set
                if propagate_ids:
                    for propagate_id in propagate_ids:
                        cur.execute(
                            """
                            UPDATE transactions
                            SET custom_description = ?,
                                category_type      = ?,
                                parent_category    = ?,
                                sub_category       = ?,
                                is_recurring       = ?
                            WHERE id = ?
                            """,
                            (custom_description, category_type, parent_category,
                             sub_category, is_recurring, propagate_id),
                        )

        # ADD A NEW MANUAL TRANSACTION
        elif action == "add_tx":
            amount = None
            date_str = (request.form.get("new_date") or "").strip()
            desc = (request.form.get("new_description") or "").strip()
            amt_str = (request.form.get("new_amount") or "").replace(",", "").strip()

            custom_description = (request.form.get("new_custom_description") or "").strip() or None
            category_type = (request.form.get("new_category_type") or "").strip() or None
            parent_category = (request.form.get("new_parent_category") or "").strip() or None
            sub_category = (request.form.get("new_sub_category") or "").strip() or None
            is_recurring_raw = request.form.get("new_is_recurring")
            is_recurring = 1 if is_recurring_raw == "1" else 0

            add_another = request.form.get("add_another") == "1"

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

                    # If "add another" is checked, return success without redirecting
                    if add_another:
                        conn.commit()
                        conn.close()
                        recalculate_current_balance()
                        return '', 204  # No content response for AJAX

        conn.commit()

        # Only recalculate balance when transactions are added/deleted/modified
        # NOT when user manually sets the balance
        if action in ["upload", "delete_duplicates", "delete_tx", "save_all", "add_tx"]:
            recalculate_current_balance()

        conn.close()

        return redirect(url_for("manage", page=page))

    current_balance = get_current_balance()

    rows, total = load_transactions(page=page, per_page=100)
    transactions = build_transaction_view(total, rows, current_balance)

    per_page = 100
    total_pages = (total + per_page - 1) // per_page if total else 0

    return render_template(
        "manage.html",
        transactions=transactions,
        current_balance=current_balance,
        error=error,
        duplicates=duplicates,
        active_tab="manage",
        page=page,
        total_pages=total_pages,
        total_transactions=total,
    )


def recalculate_current_balance():
    """
    Recalculate current balance after transaction changes.
    Uses the stored starting_balance as a baseline.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Get the starting balance (balance before any tracked transactions)
    cur.execute("SELECT value FROM settings WHERE key = 'starting_balance'")
    row = cur.fetchone()
    starting_balance = Decimal(row["value"]) if row else Decimal("0.0")

    # Sum all transactions
    cur.execute("SELECT COALESCE(SUM(CAST(amount AS REAL)), 0) FROM transactions")
    total_transactions = Decimal(str(cur.fetchone()[0]))

    # Current balance = starting balance + all transactions
    new_balance = starting_balance + total_transactions
    new_balance = normalize_amount(new_balance)  # NORMALIZE TO 2 DECIMAL PLACES

    # Update current_balance in settings
    cur.execute("""
        INSERT OR REPLACE INTO settings (key, value)
        VALUES ('current_balance', ?)
    """, (str(new_balance),))

    conn.commit()
    conn.close()

    return new_balance


# ... existing imports ...

@app.route("/export")
def export_transactions():
    """Export all transactions to CSV file"""
    conn = get_db_connection()
    cur = conn.cursor()

    # Get all transactions ordered by date
    cur.execute("""
                SELECT date_key,
                       date_raw,
                       description,
                       custom_description,
                       amount,
                       category_type,
                       parent_category,
                       sub_category,
                       is_recurring
                FROM transactions
                ORDER BY date_key DESC, id DESC
                """)

    rows = cur.fetchall()
    conn.close()

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        'Date',
        'Description',
        'Custom Description',
        'Amount',
        'Category Type',
        'Parent Category',
        'Sub Category',
        'Is Recurring'
    ])

    # Write data rows
    for row in rows:
        # Format date for display
        date_display = row['date_raw']
        try:
            if row['date_key'] and len(row['date_key']) == 10:
                d = datetime.strptime(row['date_key'], "%Y-%m-%d")
                date_display = d.strftime("%m/%d/%Y")
        except ValueError:
            pass

        writer.writerow([
            date_display,
            row['description'],
            row['custom_description'] or '',
            row['amount'],
            row['category_type'] or '',
            row['parent_category'] or '',
            row['sub_category'] or '',
            'Yes' if row['is_recurring'] else 'No'
        ])

    # Prepare file for download
    output.seek(0)

    # Generate filename with current date
    filename = f"transactions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
