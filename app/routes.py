from flask import render_template, request, redirect, url_for, send_file
import csv
import json
from io import StringIO, BytesIO
from datetime import datetime

from app.db import (
    init_db,
    get_current_balance,
    load_transactions
)
from app.helpers import (
    build_transaction_view
)
from app.handlers import (
    process_csv_upload,
    delete_transactions,
    update_multiple_transactions,
    add_manual_transaction,
    update_current_balance,
    extract_transaction_updates,
    format_export_date,
    recalculate_current_balance,
    search_transactions
)


def register_routes(app):
    """Register all application routes"""

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
        """Management page: upload CSV, edit transactions, delete transactions"""
        error = None
        duplicates = []

        if request.method == "POST":
            action = request.form.get("action")

            if action == "upload":
                uploaded_file = request.files.get("file")
                duplicates, error = process_csv_upload(uploaded_file)

            elif action == "delete_duplicates":
                delete_ids = request.form.getlist("delete_ids")
                delete_transactions(delete_ids)

            elif action == "delete_tx":
                tx_id = request.form.get("tx_id")
                if tx_id:
                    delete_transactions([tx_id])

            elif action == "save_all":
                transaction_updates = extract_transaction_updates(request.form)
                update_multiple_transactions(transaction_updates)

            elif action == "add_tx":
                date_str = request.form.get("new_date", "").strip()
                desc = request.form.get("new_description", "").strip()
                amt_str = request.form.get("new_amount", "").replace(",", "").strip()
                custom_desc = request.form.get("new_custom_description", "").strip() or None
                category_type = request.form.get("new_category_type", "").strip() or None
                parent_category = request.form.get("new_parent_category", "").strip() or None
                sub_category = request.form.get("new_sub_category", "").strip() or None
                is_recurring = 1 if request.form.get("new_is_recurring") else 0
                add_another = request.form.get("add_another") == "1"

                success, error = add_manual_transaction(
                    date_str, desc, amt_str, custom_desc, category_type,
                    parent_category, sub_category, is_recurring
                )

                # If "add another" is checked, return AJAX response
                if add_another and success:
                    return '', 204

                # If there's an error, don't redirect - show it
                if not success:
                    print(f"Error adding transaction: {error}")  # Debug log

            elif action == "bulk_search":
                description = request.form.get("search_description", "").strip()
                category_type = request.form.get("search_category_type", "").strip() or None
                parent_category = request.form.get("search_parent_category", "").strip() or None
                sub_category = request.form.get("search_sub_category", "").strip() or None
                amount_str = request.form.get("search_amount", "").replace(",", "").strip()
                exact_amount = request.form.get("search_exact_amount") == "1"
                uncategorized_only = request.form.get("search_uncategorized") == "1"

                amount = None
                if amount_str:
                    try:
                        from decimal import Decimal
                        amount = Decimal(amount_str)
                    except ValueError:
                        pass

                search_results = search_transactions(
                    description=description if description else None,
                    category_type=category_type,
                    parent_category=parent_category,
                    sub_category=sub_category,
                    amount=amount,
                    exact_amount=exact_amount,
                    uncategorized_only=uncategorized_only
                )

                # Format results for display
                current_balance = get_current_balance()
                search_transactions_list = build_transaction_view(
                    len(search_results), search_results, current_balance
                )

                # Return as JSON for AJAX
                from decimal import Decimal

                def decimal_default(obj):
                    if isinstance(obj, Decimal):
                        return float(obj)
                    raise TypeError

                return json.dumps([dict(tx) for tx in search_transactions_list], default=decimal_default)

            elif action == "bulk_update":
                from app.handlers import bulk_update_transactions

                selected_ids = request.form.getlist("selected_ids[]")
                custom_desc = request.form.get("bulk_custom_description", "").strip()
                category_type = request.form.get("bulk_category_type", "").strip()
                parent_category = request.form.get("bulk_parent_category", "").strip()
                sub_category = request.form.get("bulk_sub_category", "").strip()
                is_recurring_raw = request.form.get("bulk_is_recurring")

                # Only update fields that have values
                custom_desc = custom_desc if custom_desc else None
                category_type = category_type if category_type else None
                parent_category = parent_category if parent_category else None
                sub_category = sub_category if sub_category else None
                is_recurring = 1 if is_recurring_raw == "1" else (0 if is_recurring_raw == "0" else None)

                success, error = bulk_update_transactions(
                    selected_ids, custom_desc, category_type,
                    parent_category, sub_category, is_recurring
                )

                if success:
                    return json.dumps({"success": True, "message": f"Updated {len(selected_ids)} transaction(s)"})
                else:
                    return json.dumps({"success": False, "error": error}), 400

            # Only recalculate balance when transactions are added/deleted/modified
            if action in ["upload", "delete_duplicates", "delete_tx", "save_all", "add_tx"]:
                recalculate_current_balance()

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

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        """Settings page: balance, add transaction, upload CSV, export"""
        error = None
        duplicates = []

        if request.method == "POST":
            action = request.form.get("action")

            if action == "set_balance":
                balance_str = request.form.get("current_balance", "").replace(",", "").strip()
                success, _, error = update_current_balance(balance_str)

            elif action == "upload":
                uploaded_file = request.files.get("file")
                duplicates, error = process_csv_upload(uploaded_file)

            return redirect(url_for("settings"))

        current_balance = get_current_balance()

        return render_template(
            "settings.html",
            current_balance=current_balance,
            error=error,
            duplicates=duplicates,
            active_tab="settings"
        )

    @app.route("/export")
    def export_transactions():
        """Export all transactions to CSV file"""
        from app.db import get_db_connection

        conn = get_db_connection()
        cur = conn.cursor()

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
        output = StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Date', 'Description', 'Custom Description', 'Amount',
            'Category Type', 'Parent Category', 'Sub Category', 'Is Recurring'
        ])

        # Write data rows
        for row in rows:
            date_display = format_export_date(row['date_key'], row['date_raw'])
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

        output.seek(0)
        filename = f"transactions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return send_file(
            BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

    @app.route("/budget", methods=["GET", "POST"])
    def budget():
        """Budget management page"""
        from app.db import get_budget_items, import_recurring_transactions_to_budget
        from app.budget_helpers import (
            categorize_budget_items_by_period,
            calculate_period_totals,
            get_current_period
        )
        from app.handlers import (
            process_add_budget_item,
            process_update_budget_item,
            process_delete_budget_item
        )

        error = None
        success_message = None

        if request.method == "POST":
            action = request.form.get("action")

            if action == "add_item":
                success, error = process_add_budget_item(request.form)
                if success:
                    print("Budget item added successfully!")

            elif action == "update_item":
                success, error = process_update_budget_item(request.form)
                if success:
                    print("Budget item updated successfully!")

            elif action == "delete_item":
                item_id = request.form.get("item_id")
                success, error = process_delete_budget_item(item_id)
                if success:
                    print("Budget item deleted successfully!")

            elif action == "import_recurring":
                imported_count = import_recurring_transactions_to_budget()
                print(f"Imported {imported_count} recurring transaction(s) to budget.")

            return redirect(url_for("budget"))

        # Get all budget items
        budget_items = get_budget_items()

        # Categorize by period
        period1_items, period2_items = categorize_budget_items_by_period(budget_items)

        # Calculate totals
        period1_income, period1_expenses = calculate_period_totals(period1_items)
        period2_income, period2_expenses = calculate_period_totals(period2_items)

        current_period = get_current_period()

        return render_template(
            "budget.html",
            period1_items=period1_items,
            period2_items=period2_items,
            period1_income=period1_income,
            period1_expenses=period1_expenses,
            period2_income=period2_income,
            period2_expenses=period2_expenses,
            current_period=current_period,
            error=error,
            success_message=success_message,
            active_tab="budget"
        )
