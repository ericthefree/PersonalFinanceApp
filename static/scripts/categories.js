// Shared category hierarchy and functions

const CATEGORY_HIERARCHY = {
    "Income": {
        "Employment": ["Salary", "Bonus", "Commission"],
        "Business": ["Sales", "Services", "Consulting"],
        "Investments": ["Dividends", "Interest", "Capital Gains"],
        "Other": ["Gifts", "Refunds", "Miscellaneous"]
    },
    "Bills": {
        "Housing": ["Rent/Mortgage", "Property Tax", "HOA Fees", "Insurance"],
        "Utilities": ["Electric", "Gas", "Water", "Internet", "Phone"],
        "Insurance": ["Health", "Auto", "Life", "Home", "Legal", "Identity Theft"],
        "Subscriptions": ["Streaming", "Software", "Memberships"]
    },
    "Expenses": {
        "Food": ["Groceries", "Restaurants", "Fast Food", "Coffee", "Drinks & Snacks"],
        "Transportation": ["Gas", "Parking", "Public Transit", "Rideshare"],
        "Shopping": ["Clothing", "Electronics", "Home Goods", "Personal Care"],
        "Personal Care": ["Hair", "Beauty", "Health", "Fitness"],
        "Entertainment": ["Movies", "Events", "Hobbies", "Games"],
        "Healthcare": ["Doctor", "Pharmacy", "Dental", "Vision"],
        "Other": ["Miscellaneous"]
    },
    "Debts": {
        "Credit Cards": ["Payment", "Interest"],
        "Loans": ["Auto Loan", "Student Loan", "Personal Loan"],
        "Mortgage": ["Principal", "Interest"]
    },
    "Investments": {
        "Retirement": ["401k", "IRA", "Roth IRA"],
        "Brokerage": ["Stocks", "Bonds", "ETFs", "Mutual Funds"],
        "Savings": ["Emergency Fund", "Goal Savings"]
    },
    "Transfers": {
        "Between Accounts": ["Checking to Savings", "Savings to Checking"],
        "External": ["To Other Person", "From Other Person"]
    }
};

function initCategoryRow(txId) {
    const typeSelect = document.querySelector(`.category-type-input[data-tx-id="${txId}"]`);
    const parentSelect = document.querySelector(`.parent-category-input[data-tx-id="${txId}"]`);
    const subSelect = document.querySelector(`.sub-category-input[data-tx-id="${txId}"]`);

    if (!typeSelect || !parentSelect || !subSelect) return;

    const currentType = typeSelect.value;

    // Read current parent and sub from their respective elements, not from type select
    const currentParent = parentSelect.getAttribute("data-current") ||
                         typeSelect.getAttribute("data-current-parent") || "";
    const currentSub = subSelect.getAttribute("data-current") ||
                      typeSelect.getAttribute("data-current-sub") || "";

    if (currentType) {
        populateParentOptions(currentType, parentSelect, currentParent);
        if (currentParent) {
            populateSubOptions(currentType, currentParent, subSelect, currentSub);
        }
    }

    // Add change listeners to cascade updates
    typeSelect.addEventListener("change", function() {
        const newType = this.value;
        parentSelect.setAttribute("data-current", "");
        subSelect.setAttribute("data-current", "");
        populateParentOptions(newType, parentSelect, "");
        populateSubOptions(newType, "", subSelect, "");
    });

    parentSelect.addEventListener("change", function() {
        const newParent = this.value;
        subSelect.setAttribute("data-current", "");
        populateSubOptions(typeSelect.value, newParent, subSelect, "");
    });
}

function populateParentOptions(categoryType, parentSelect, currentParent) {
    // Clear existing options
    parentSelect.innerHTML = '<option value=""></option>';

    if (!categoryType || !CATEGORY_HIERARCHY[categoryType]) return;

    const parents = Object.keys(CATEGORY_HIERARCHY[categoryType]);
    parents.forEach(parent => {
        const option = document.createElement("option");
        option.value = parent;
        option.textContent = parent;
        if (parent === currentParent) {
            option.selected = true;
        }
        parentSelect.appendChild(option);
    });
}

function populateSubOptions(categoryType, parentCategory, subSelect, currentSub) {
    // Clear existing options
    subSelect.innerHTML = '<option value=""></option>';

    if (!categoryType || !parentCategory || !CATEGORY_HIERARCHY[categoryType]) return;

    const subs = CATEGORY_HIERARCHY[categoryType][parentCategory];
    if (!subs) return;

    subs.forEach(sub => {
        const option = document.createElement("option");
        option.value = sub;
        option.textContent = sub;
        if (sub === currentSub) {
            option.selected = true;
        }
        subSelect.appendChild(option);
    });
}
