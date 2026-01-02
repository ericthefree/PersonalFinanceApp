from flask import render_template, request, redirect, url_for, send_file
import csv
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
    recalculate_current_balance
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
