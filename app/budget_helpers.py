"""Helper functions for budget calculations and formatting"""
from datetime import datetime, date
from decimal import Decimal
from calendar import monthrange


def get_current_period():
    """Get the current budget period (1 or 2)"""
    today = date.today()
    return 1 if today.day <= 14 else 2


def get_period_dates(year, month, period):
    """
    Get start and end dates for a budget period.
    Period 1: 1st-14th
    Period 2: 15th-end of month
    """
    if period == 1:
        start_date = date(year, month, 1)
        end_date = date(year, month, 14)
    else:
        start_date = date(year, month, 15)
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)

    return start_date, end_date


def categorize_budget_items_by_period(budget_items):
    """
    Categorize budget items into periods based on day of month.
    Returns: (period1_items, period2_items)
    """
    period1_items = []
    period2_items = []

    for item in budget_items:
        if item['day_of_month'] <= 14:
            period1_items.append(item)
        else:
            period2_items.append(item)

    return period1_items, period2_items


def calculate_period_totals(items):
    """Calculate total income and expenses for a list of budget items"""
    from decimal import Decimal
    from app.helpers import normalize_amount

    income_total = Decimal('0')
    expense_total = Decimal('0')

    for item in items:
        amount = Decimal(str(item['amount']))
        amount = normalize_amount(amount)

        if amount > 0:
            income_total += amount
        else:
            expense_total += abs(amount)

    # Normalize final totals
    income_total = normalize_amount(income_total)
    expense_total = normalize_amount(expense_total)

    return income_total, expense_total


def is_item_due_this_period(item, year, month, period):
    """Check if a budget item is due in the specified period"""
    frequency = item['frequency']
    day_of_month = item['day_of_month']

    # Monthly items are always due
    if frequency == 'monthly':
        start_date, end_date = get_period_dates(year, month, period)
        item_date = date(year, month, min(day_of_month, end_date.day))
        return start_date <= item_date <= end_date

    # For non-monthly items, check next_due_date
    if item['next_due_date']:
        try:
            next_due = datetime.strptime(item['next_due_date'], '%Y-%m-%d').date()
            start_date, end_date = get_period_dates(year, month, period)
            return start_date <= next_due <= end_date
        except (ValueError, TypeError):
            return False

    return False


def format_frequency_display(frequency):
    """Format frequency for display"""
    frequency_map = {
        'monthly': 'Monthly',
        'quarterly': 'Quarterly',
        'semi-annually': 'Every 6 Months',
        'annually': 'Yearly'
    }
    return frequency_map.get(frequency, frequency.capitalize())


def calculate_next_due_date(frequency, current_date, day_of_month):
    """Calculate the next due date based on frequency"""
    if frequency == 'monthly':
        return None  # Monthly items don't need next_due_date

    year = current_date.year
    month = current_date.month

    if frequency == 'quarterly':
        # Add 3 months
        month += 3
        if month > 12:
            month -= 12
            year += 1
    elif frequency == 'semi-annually':
        # Add 6 months
        month += 6
        if month > 12:
            month -= 12
            year += 1
    elif frequency == 'annually':
        # Add 1 year
        year += 1

    # Adjust day if it exceeds days in the target month
    _, last_day = monthrange(year, month)
    day = min(day_of_month, last_day)

    return date(year, month, day).isoformat()
