"""Business logic handlers for transaction operations"""
import csv
from io import TextIOWrapper
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.db import get_db_connection, recalculate_current_balance
from app.helpers import parse_date, normalize_amount


def process_csv_upload(uploaded_file):
    """
    Process uploaded CSV file and return duplicates found.
    Returns: (duplicates_list, error_message)
    """
    if not uploaded_file or not uploaded_file.filename:
        return [], "No file uploaded"

    duplicates = []
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Get all existing transaction IDs before import
        cur.execute("SELECT id FROM transactions")
        pre_import_ids = {row["id"] for row in cur.fetchall()}

        wrapper = TextIOWrapper(uploaded_file.stream, encoding="utf-8-sig")
        reader = csv.DictReader(wrapper)
        seen_duplicate_ids = set()

        for row in reader:
            transaction_data = extract_csv_row_data(row)
            if not transaction_data:
                continue

            date_key, date_raw, desc, amount_str = transaction_data

            # Check for duplicates
            duplicate_id = find_duplicate_transaction(
                cur, date_key, desc, amount_str, pre_import_ids, seen_duplicate_ids
            )

            if duplicate_id:
                seen_duplicate_ids.add(duplicate_id)
                duplicates.append(format_duplicate_entry(cur, duplicate_id))
            else:
                # Insert new transaction
                insert_transaction(cur, date_key, date_raw, desc, amount_str)

        conn.commit()
        recalculate_current_balance()

    except Exception as e:
        conn.rollback()
        return [], f"Error processing CSV: {str(e)}"
    finally:
        conn.close()

    return duplicates, None


def extract_csv_row_data(row):
    """
    Extract and validate data from a CSV row.
    Returns: (date_key, date_raw, description, amount_str) or None if invalid
    """
    date_str = row.get("date") or row.get("Date") or row.get("DATE")
    desc = row.get("description") or row.get("Description") or row.get("DESCRIPTION")
    amt_str = row.get("amount") or row.get("Amount") or row.get("AMOUNT")

    if not (date_str and desc and amt_str):
        return None

    date_str = date_str.strip()
    desc = desc.strip()

    date_obj = parse_date(date_str)

    try:
        amount = Decimal(amt_str.replace(",", "").strip())
        amount = normalize_amount(amount)
        amount_str = str(amount)
    except InvalidOperation:
        return None

    if date_obj:
        date_key = date_obj.date().isoformat()
        date_raw = date_str
    else:
        date_key = date_str
        date_raw = date_str

    return date_key, date_raw, desc, amount_str


def find_duplicate_transaction(cur, date_key, description, amount, pre_import_ids, seen_ids):
    """
    Check if transaction is a duplicate.
    Returns: duplicate_id if found, None otherwise
    """
    cur.execute(
        """
        SELECT id
        FROM transactions
        WHERE date_key = ?
          AND description = ?
          AND amount = ?
        """,
        (date_key, description, amount),
    )
    existing_rows = cur.fetchall()

    # Filter to only pre-import transactions not already marked
    available_duplicates = [
        row for row in existing_rows
        if row["id"] in pre_import_ids and row["id"] not in seen_ids
    ]

    return available_duplicates[0]["id"] if available_duplicates else None


def format_duplicate_entry(cur, transaction_id):
    """Format a duplicate transaction for display"""
    cur.execute(
        "SELECT date_key, date_raw, description, amount FROM transactions WHERE id = ?",
        (transaction_id,)
    )
    row = cur.fetchone()

    duplicate_date_display = row["date_raw"]
    try:
        if row["date_key"] and len(row["date_key"]) == 10:
            d = datetime.strptime(row["date_key"], "%Y-%m-%d")
            duplicate_date_display = d.strftime("%d-%b-%y")
    except ValueError:
        pass

    return {
        "id": transaction_id,
        "date_display": duplicate_date_display,
        "description": row["description"],
        "amount": Decimal(row["amount"]),
    }


def insert_transaction(cur, date_key, date_raw, description, amount,
                       custom_description=None, category_type=None,
                       parent_category=None, sub_category=None, is_recurring=0):
    """Insert a new transaction into the database"""
    cur.execute(
        """
        INSERT INTO transactions
        (date_key, date_raw, description, amount, custom_description,
         category_type, parent_category, sub_category, is_recurring)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (date_key, date_raw, description, amount, custom_description,
         category_type, parent_category, sub_category, is_recurring),
    )


def delete_transactions(transaction_ids):
    """Delete multiple transactions by ID"""
    if not transaction_ids:
        return False

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.executemany("DELETE FROM transactions WHERE id = ?",
                        [(tid,) for tid in transaction_ids])
        conn.commit()
        recalculate_current_balance()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def update_transaction(transaction_id, custom_description=None, category_type=None,
                       parent_category=None, sub_category=None, is_recurring=0):
    """Update a single transaction's metadata"""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
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
             sub_category, is_recurring, transaction_id),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def update_multiple_transactions(transaction_updates):
    """
    Update multiple transactions in bulk.
    transaction_updates: list of dicts with 'id' and metadata fields
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        for update in transaction_updates:
            tx_id = update['id']
            custom_desc = update.get('custom_description')
            category_type = update.get('category_type')
            parent_category = update.get('parent_category')
            sub_category = update.get('sub_category')
            is_recurring = update.get('is_recurring', 0)
            propagate_ids = update.get('propagate_to', [])

            # Update main transaction
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
                (custom_desc, category_type, parent_category,
                 sub_category, is_recurring, tx_id),
            )

            # Update similar transactions if propagate_to is set
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
                    (custom_desc, category_type, parent_category,
                     sub_category, is_recurring, propagate_id),
                )

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def add_manual_transaction(date_str, description, amount_str,
                           custom_description=None, category_type=None,
                           parent_category=None, sub_category=None, is_recurring=0):
    """
    Add a manual transaction.
    Returns: (success, error_message)
    """
    if not (date_str and description and amount_str):
        return False, "Date, description, and amount are required."

    date_obj = parse_date(date_str)

    try:
        amount = Decimal(amount_str.replace(",", "").strip())
        amount = normalize_amount(amount)
    except (InvalidOperation, ValueError):
        return False, "Amount must be a valid number."

    if date_obj:
        date_key = date_obj.date().isoformat()
        date_raw = date_str
    else:
        date_key = date_str
        date_raw = date_str

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        insert_transaction(
            cur, date_key, date_raw, description, str(amount),
            custom_description, category_type, parent_category,
            sub_category, is_recurring
        )
        conn.commit()
        recalculate_current_balance()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, f"Error adding transaction: {str(e)}"
    finally:
        conn.close()


def update_current_balance(balance_str):
    """
    Update the current balance and calculate starting balance.
    Returns: (success, new_balance, error_message)
    """
    from app.db import set_current_balance, get_db_connection

    if not balance_str:
        return False, None, "Current balance is required."

    try:
        balance = Decimal(balance_str.replace(",", "").strip())
        balance = normalize_amount(balance)
    except (InvalidOperation, ValueError):
        return False, None, "Current balance must be a valid number."

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Calculate starting balance
        cur.execute("SELECT COALESCE(SUM(CAST(amount AS REAL)), 0) FROM transactions")
        total_transactions = Decimal(str(cur.fetchone()[0]))
        total_transactions = normalize_amount(total_transactions)

        starting_balance = balance - total_transactions
        starting_balance = normalize_amount(starting_balance)

        # Store both values
        set_current_balance(balance)
        cur.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('starting_balance', ?)",
            (str(starting_balance),)
        )
        conn.commit()
        return True, balance, None
    except Exception as e:
        conn.rollback()
        return False, None, f"Error updating balance: {str(e)}"
    finally:
        conn.close()


def extract_transaction_updates(form_data):
    """Extract transaction updates from form data"""
    row_ids = form_data.getlist("row_id")
    updates = []

    for row_id in row_ids:
        custom_desc = (form_data.get(f"custom_description_{row_id}") or "").strip() or None
        category_type = (form_data.get(f"category_type_{row_id}") or "").strip() or None
        parent_category = (form_data.get(f"parent_category_{row_id}") or "").strip() or None
        sub_category = (form_data.get(f"sub_category_{row_id}") or "").strip() or None
        is_recurring = 1 if form_data.get(f"is_recurring_{row_id}") else 0

        propagate_to_str = form_data.get(f"propagate_to_{row_id}", "")
        propagate_ids = [x.strip() for x in propagate_to_str.split(",") if x.strip()]

        updates.append({
            'id': row_id,
            'custom_description': custom_desc,
            'category_type': category_type,
            'parent_category': parent_category,
            'sub_category': sub_category,
            'is_recurring': is_recurring,
            'propagate_to': propagate_ids
        })

    return updates


def format_export_date(date_key, date_raw):
    """Format date for CSV export"""
    try:
        if date_key and len(date_key) == 10:
            d = datetime.strptime(date_key, "%Y-%m-%d")
            return d.strftime("%m/%d/%Y")
    except ValueError:
        pass
    return date_raw


def process_add_budget_item(form_data):
    """Process adding a new budget item"""
    from app.db import add_budget_item
    from decimal import Decimal, InvalidOperation

    description = form_data.get('description', '').strip()
    amount_str = form_data.get('amount', '').replace(',', '').strip()
    day_of_month = form_data.get('day_of_month', '').strip()
    frequency = form_data.get('frequency', 'monthly').strip()
    next_due_date = form_data.get('next_due_date', '').strip() or None
    category_type = form_data.get('category_type', '').strip() or None
    parent_category = form_data.get('parent_category', '').strip() or None
    sub_category = form_data.get('sub_category', '').strip() or None
    notes = form_data.get('notes', '').strip() or None

    if not description or not amount_str or not day_of_month:
        return False, "Description, amount, and day of month are required."

    try:
        amount = Decimal(amount_str)
        day = int(day_of_month)

        if day < 1 or day > 31:
            return False, "Day of month must be between 1 and 31."

    except (InvalidOperation, ValueError):
        return False, "Invalid amount or day of month."

    try:
        add_budget_item(
            description, str(amount), day, frequency, next_due_date,
            category_type, parent_category, sub_category, notes
        )
        return True, None
    except Exception as e:
        return False, f"Error adding budget item: {str(e)}"


def process_update_budget_item(form_data):
    """Process updating a budget item"""
    from app.db import update_budget_item
    from decimal import Decimal, InvalidOperation

    item_id = form_data.get('item_id')
    description = form_data.get('description', '').strip()
    amount_str = form_data.get('amount', '').replace(',', '').strip()
    day_of_month = form_data.get('day_of_month', '').strip()
    frequency = form_data.get('frequency', 'monthly').strip()
    next_due_date = form_data.get('next_due_date', '').strip() or None
    category_type = form_data.get('category_type', '').strip() or None
    parent_category = form_data.get('parent_category', '').strip() or None
    sub_category = form_data.get('sub_category', '').strip() or None
    notes = form_data.get('notes', '').strip() or None

    if not item_id:
        return False, "Item ID is required."

    if not description or not amount_str or not day_of_month:
        return False, "Description, amount, and day of month are required."

    try:
        amount = Decimal(amount_str)
        day = int(day_of_month)

        if day < 1 or day > 31:
            return False, "Day of month must be between 1 and 31."

    except (InvalidOperation, ValueError):
        return False, "Invalid amount or day of month."

    try:
        update_budget_item(
            item_id, description, str(amount), day, frequency, next_due_date,
            category_type, parent_category, sub_category, notes
        )
        return True, None
    except Exception as e:
        return False, f"Error updating budget item: {str(e)}"


def process_delete_budget_item(item_id):
    """Process deleting a budget item"""
    from app.db import delete_budget_item

    if not item_id:
        return False, "Item ID is required."

    try:
        delete_budget_item(item_id)
        return True, None
    except Exception as e:
        return False, f"Error deleting budget item: {str(e)}"


def search_transactions(description=None, category_type=None, parent_category=None,
                        sub_category=None, amount=None, exact_amount=False,
                        uncategorized_only=False):
    """
    Search transactions based on criteria.
    Returns list of matching transactions.
    """
    from app.db import get_db_connection
    from decimal import Decimal

    conn = get_db_connection()
    cur = conn.cursor()

    query = "SELECT * FROM transactions WHERE 1=1"
    params = []

    if uncategorized_only:
        query += " AND (category_type IS NULL OR category_type = '')"
        query += " AND (parent_category IS NULL OR parent_category = '')"
        query += " AND (sub_category IS NULL OR sub_category = '')"
    else:
        if description:
            query += " AND description LIKE ?"
            params.append(f"%{description}%")

        if category_type:
            query += " AND category_type = ?"
            params.append(category_type)

        if parent_category:
            query += " AND parent_category = ?"
            params.append(parent_category)

        if sub_category:
            query += " AND sub_category = ?"
            params.append(sub_category)

        if amount:
            amount_decimal = Decimal(str(amount))

            if exact_amount:
                # Search for both positive and negative exact amounts
                query += " AND (CAST(amount AS REAL) = ? OR CAST(amount AS REAL) = ?)"
                params.append(float(amount_decimal))
                params.append(float(-amount_decimal))
            else:
                # Search within -$2 to +$5 for both positive and negative amounts
                min_amount_pos = float(amount_decimal - Decimal('2'))
                max_amount_pos = float(amount_decimal + Decimal('5'))
                min_amount_neg = float(-amount_decimal - Decimal('5'))
                max_amount_neg = float(-amount_decimal + Decimal('2'))

                query += " AND ((CAST(amount AS REAL) BETWEEN ? AND ?) OR (CAST(amount AS REAL) BETWEEN ? AND ?))"
                params.append(min_amount_pos)
                params.append(max_amount_pos)
                params.append(min_amount_neg)
                params.append(max_amount_neg)

    query += " ORDER BY date_key DESC, id DESC"

    cur.execute(query, params)
    results = cur.fetchall()
    conn.close()

    return results


def bulk_update_transactions(transaction_ids, custom_description=None,
                             category_type=None, parent_category=None,
                             sub_category=None, is_recurring=None):
    """
    Bulk update multiple transactions.
    Only updates fields that are provided (not None).
    """
    from app.db import get_db_connection, recalculate_current_balance

    if not transaction_ids:
        return False, "No transactions selected."

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Build dynamic UPDATE query based on provided fields
        update_fields = []
        params = []

        if custom_description is not None:
            update_fields.append("custom_description = ?")
            params.append(custom_description if custom_description else None)

        if category_type is not None:
            update_fields.append("category_type = ?")
            params.append(category_type if category_type else None)

        if parent_category is not None:
            update_fields.append("parent_category = ?")
            params.append(parent_category if parent_category else None)

        if sub_category is not None:
            update_fields.append("sub_category = ?")
            params.append(sub_category if sub_category else None)

        if is_recurring is not None:
            update_fields.append("is_recurring = ?")
            params.append(is_recurring)

        if not update_fields:
            return False, "No fields to update."

        # Update each transaction
        for tx_id in transaction_ids:
            query = f"UPDATE transactions SET {', '.join(update_fields)} WHERE id = ?"
            cur.execute(query, params + [tx_id])

        conn.commit()
        recalculate_current_balance()
        return True, None

    except Exception as e:
        conn.rollback()
        return False, f"Error updating transactions: {str(e)}"
    finally:
        conn.close()
