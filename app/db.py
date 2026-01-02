import sqlite3
from pathlib import Path
from decimal import Decimal

DB_PATH = Path("instance/transactions.db")


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
                CREATE TABLE IF NOT EXISTS transactions
                (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    date_key    TEXT NOT NULL,
                    date_raw    TEXT NOT NULL,
                    description TEXT NOT NULL,
                    amount      REAL NOT NULL
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
                CREATE TABLE IF NOT EXISTS settings
                (
                    key   TEXT PRIMARY KEY,
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


def recalculate_current_balance():
    """
    Recalculate current balance after transaction changes.
    Uses the stored starting_balance as a baseline.
    """
    from app.helpers import normalize_amount

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
    new_balance = normalize_amount(new_balance)

    # Update current_balance in settings
    cur.execute("""
        INSERT OR REPLACE INTO settings (key, value)
        VALUES ('current_balance', ?)
    """, (str(new_balance),))

    conn.commit()
    conn.close()

    return new_balance


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
