from datetime import datetime
from decimal import Decimal, InvalidOperation


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


def normalize_amount(value) -> Decimal:
    """Normalize to 2 decimal places."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(Decimal("0.01"))


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
