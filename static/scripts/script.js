// CATEGORY_MAP based on your provided structure
const CATEGORY_MAP = {
  Income: {
    "Primary Income": [
      "Salary",
      "Bonus",
      "Stock"
    ],
    "Other Income": [
      "Interest Income",
      "Dividends",
      "Refunds",
      "Reimbursements",
      "Gifts",
      "Transfer from Savings",
      "Tax Refund"
    ]
  },
  Bills: {
    "Housing": [
      "Mortgage/Rent",
      "HOA Dues",
      "Home Insurance",
      "Home Maintenance"
    ],
    "Utilities": [
      "Electricity",
      "Water/Sewer",
      "Natural Gas",
      "Trash/Recycling",
      "Internet",
      "Streaming Services",
      "Mobile Phone"
    ],
    "Transportation": [
      "Insurance",
      "Registration/Licensing",
      "Parking",
      "Maintenance"
    ],
    "Subscriptions": [
      "Music",
      "Movie Streaming Services",
      "Cloud Storage",
      "Software/Tech",
      "News/Education"
    ]
  },

  Expenses: {
    "Groceries & Dining": [
      "Groceries",
      "Dining Out",
      "Coffee/Snacks",
      "Bars"
    ],
    "Health & Wellness": [
      "Medical Bills",
      "Prescriptions",
      "Vitamins/Supplements",
      "Gym Membership",
      "Dental",
      "Eye Care",
      "Chiropractic",
      "Massage"
    ],
    "Personal Care": [
      "Haircuts",
      "Clothing",
      "Toiletries"
    ],
    "Household": [
      "Cleaning Supplies",
      "Furniture/Decor",
      "Tools/Maintenance"
    ],
    "Entertainment & Hobbies": [
      "Movies/Games/Books",
      "Sports/Activities",
      "Events/Concerts"
    ],
    "Education": [
      "Courses/Training",
      "Books/Materials",
      "Tuition Payments"
    ]
  },

  Debts: {
    "Credit Cards": [
      "Visa/Mastercard/Amex",
      "Store Card"
    ],
    "Loans": [
      "Student Loans",
      "Auto Loan",
      "Personal Loan",
      "Debt Consolidation"
    ]
  },

  Investments: {
    "Emergency Fund": [
      "Rainy Day Fund",
      "3–6 Month Reserve"
    ],
    "Short-Term Savings": [
      "Vacation Fund",
      "Holiday Gifts",
      "Home Improvement"
    ],
    "Long-Term Savings": [
      "Retirement (401k, IRA)",
      "Investment Account",
      "College Fund"
    ],
    "Transfers": [
      "To Savings Account",
      "From Savings Account"
    ]
  },

  Transfers: {
    "Internal Transfers": [
      "Checking ↔ Savings",
      "Bank Fees",
      "Credit Payment"
    ],
    "Adjustments": [
      "Balance Adjustment",
      "Bank Error Correction"
    ]
  }
};


// Populate parent category options based on category type
function populateParentOptions(typeValue, parentSelect, currentParent) {
    if (!parentSelect) return;

    parentSelect.innerHTML = "";
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "";
    parentSelect.appendChild(blank);

    if (!typeValue || !CATEGORY_MAP[typeValue]) {
        return;
    }

    const parents = Object.keys(CATEGORY_MAP[typeValue]);
    parents.forEach(parent => {
        const opt = document.createElement("option");
        opt.value = parent;
        opt.textContent = parent;
        if (parent === currentParent) {
            opt.selected = true;
        }
        parentSelect.appendChild(opt);
    });
}


// Populate subcategory options based on type + parent
function populateSubOptions(typeValue, parentValue, subSelect, currentSub) {
    if (!subSelect) return;

    subSelect.innerHTML = "";
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "";
    subSelect.appendChild(blank);

    if (!typeValue || !parentValue) return;
    const typeObj = CATEGORY_MAP[typeValue];
    if (!typeObj || !typeObj[parentValue]) return;

    typeObj[parentValue].forEach(sub => {
        const opt = document.createElement("option");
        opt.value = sub;
        opt.textContent = sub;
        if (sub === currentSub) {
            opt.selected = true;
        }
        subSelect.appendChild(opt);
    });
}


// Initialize a row's category selects based on data attributes
function initCategoryRow(txId) {
    const typeSelect = document.querySelector(`.category-type-input[data-tx-id="${txId}"]`);
    const parentSelect = document.querySelector(`.parent-category-input[data-tx-id="${txId}"]`);
    const subSelect = document.querySelector(`.sub-category-input[data-tx-id="${txId}"]`);

    if (!typeSelect || !parentSelect || !subSelect) return;

    const currentParent = parentSelect.getAttribute("data-current") ||
                          typeSelect.getAttribute("data-current-parent") ||
                          "";
    const currentSub = subSelect.getAttribute("data-current") ||
                       typeSelect.getAttribute("data-current-sub") ||
                       "";

    populateParentOptions(typeSelect.value, parentSelect, currentParent);
    populateSubOptions(typeSelect.value, currentParent, subSelect, currentSub);

    // Initial tooltips for selects
    updateFieldTooltip(typeSelect);
    updateFieldTooltip(parentSelect);
    updateFieldTooltip(subSelect);
}


// Build group mapping for similar transactions: same description + amount
function buildSimilarGroups() {
    const groupMap = {};
    const rowMeta = {};

    const rows = document.querySelectorAll("tr.transaction-row[data-tx-id]");
    rows.forEach(row => {
        const txId = row.getAttribute("data-tx-id");
        if (!txId || txId === "new") return;

        const desc = row.getAttribute("data-description") || "";
        const amount = row.getAttribute("data-amount") || "";
        const date = row.getAttribute("data-date") || "";

        const key = desc + "::" + amount;
        if (!groupMap[key]) {
            groupMap[key] = [];
        }
        groupMap[key].push(txId);
        rowMeta[txId] = { desc, amount, date };
    });

    return { groupMap, rowMeta };
}


// Update hidden propagate_to_<id> based on selected checkboxes in panel
function updatePropagateHidden(txId) {
    const hidden = document.getElementById(`propagate-to-${txId}`);
    if (!hidden) return;

    const boxes = document.querySelectorAll(`.similar-checkbox[data-source-id="${txId}"]`);
    const selected = Array.from(boxes)
        .filter(b => b.checked)
        .map(b => b.getAttribute("data-target-id"));

    hidden.value = selected.join(",");
}


// Show similar transactions panel for a given row id
function showSimilarPanel(txId, groupMap, rowMeta) {
    const row = document.querySelector(`tr.transaction-row[data-tx-id="${txId}"]`);
    if (!row) return;

    const desc = row.getAttribute("data-description") || "";
    const amount = row.getAttribute("data-amount") || "";
    const key = desc + "::" + amount;

    const group = groupMap[key] || [];
    const others = group.filter(id => id !== txId);
    if (others.length === 0) {
        return;
    }

    const panel = document.querySelector(`.similar-panel[data-tx-id="${txId}"]`);
    if (!panel) return;

    const itemsHtml = others.map(id => {
        const meta = rowMeta[id] || {};
        const labelText = `${meta.date || ""} — ${meta.desc || ""} — ${meta.amount || ""}`;
        return `
            <li>
                <label>
                    <input type="checkbox"
                           class="similar-checkbox"
                           data-source-id="${txId}"
                           data-target-id="${id}">
                    ${labelText}
                </label>
            </li>
        `;
    }).join("");

    panel.innerHTML = `
        <div class="similar-panel-header">
            <span>Apply these changes to similar transactions?</span>
            <label>
                <input type="checkbox"
                       class="similar-select-all"
                       data-source-id="${txId}">
                Select all
            </label>
        </div>
        <ul class="similar-list">
            ${itemsHtml}
        </ul>
    `;

    panel.style.display = "block";

    const selectAll = panel.querySelector(`.similar-select-all[data-source-id="${txId}"]`);
    if (selectAll) {
        selectAll.addEventListener("change", function () {
            const boxes = panel.querySelectorAll(`.similar-checkbox[data-source-id="${txId}"]`);
            boxes.forEach(b => {
                b.checked = selectAll.checked;
            });
            updatePropagateHidden(txId);
        });
    }

    const checkboxes = panel.querySelectorAll(`.similar-checkbox[data-source-id="${txId}"]`);
    checkboxes.forEach(box => {
        box.addEventListener("change", function () {
            updatePropagateHidden(txId);
        });
    });
}


// Tooltip helper
function updateFieldTooltip(el) {
    if (!el) return;
    if (el.tagName === "INPUT") {
        el.title = el.value || "";
    } else if (el.tagName === "SELECT") {
        const opt = el.options[el.selectedIndex];
        el.title = opt ? opt.textContent : "";
    }
}


document.addEventListener("DOMContentLoaded", function () {
    // Delete confirmation on manage page
    const deleteForms = document.querySelectorAll("form.delete-form");
    deleteForms.forEach(form => {
        form.addEventListener("submit", function (e) {
            const confirmed = confirm("Are you sure you want to delete this transaction?");
            if (!confirmed) {
                e.preventDefault();
            }
        });
    });

    // Initialize category selectors (including the "new" row)
    const typeSelects = document.querySelectorAll(".category-type-input");
    typeSelects.forEach(select => {
        const txId = select.getAttribute("data-tx-id");
        if (txId) {
            initCategoryRow(txId);
        }
    });

    const { groupMap, rowMeta } = buildSimilarGroups();

    // Type changes: update parent/sub + similar panel + tooltip
    typeSelects.forEach(select => {
        select.addEventListener("change", function () {
            const txId = select.getAttribute("data-tx-id");
            const parentSelect = document.querySelector(`.parent-category-input[data-tx-id="${txId}"]`);
            const subSelect = document.querySelector(`.sub-category-input[data-tx-id="${txId}"]`);
            if (!parentSelect || !subSelect) return;

            parentSelect.setAttribute("data-current", "");
            subSelect.setAttribute("data-current", "");

            populateParentOptions(select.value, parentSelect, "");
            populateSubOptions(select.value, "", subSelect, "");

            updateFieldTooltip(select);

            if (txId !== "new") {
                showSimilarPanel(txId, groupMap, rowMeta);
            }
        });

        // Initial tooltip for type select
        updateFieldTooltip(select);
    });

    // Parent changes: update sub + similar panel + tooltip
    const parentSelects = document.querySelectorAll(".parent-category-input");
    parentSelects.forEach(parentSelect => {
        parentSelect.addEventListener("change", function () {
            const txId = parentSelect.getAttribute("data-tx-id");
            const typeSelect = document.querySelector(`.category-type-input[data-tx-id="${txId}"]`);
            const subSelect = document.querySelector(`.sub-category-input[data-tx-id="${txId}"]`);
            if (!typeSelect || !subSelect) return;

            subSelect.setAttribute("data-current", "");
            populateSubOptions(typeSelect.value, parentSelect.value, subSelect, "");

            updateFieldTooltip(parentSelect);

            if (txId !== "new") {
                showSimilarPanel(txId, groupMap, rowMeta);
            }
        });

        // Initial tooltip
        updateFieldTooltip(parentSelect);
    });

    // Subcategory changes: show similar panel + tooltip
    const subSelects = document.querySelectorAll(".sub-category-input");
    subSelects.forEach(subSelect => {
        subSelect.addEventListener("change", function () {
            const txId = subSelect.getAttribute("data-tx-id");
            updateFieldTooltip(subSelect);
            if (!txId || txId === "new") return;
            showSimilarPanel(txId, groupMap, rowMeta);
        });

        updateFieldTooltip(subSelect);
    });

    // Custom description changes: show similar panel + tooltip
    const customInputs = document.querySelectorAll(".custom-desc-input");
    customInputs.forEach(input => {
        updateFieldTooltip(input);

        input.addEventListener("input", function () {
            const txId = input.getAttribute("data-tx-id");
            updateFieldTooltip(input);
            if (!txId || txId === "new") return;
            showSimilarPanel(txId, groupMap, rowMeta);
        });
    });

    // Recurring checkbox tooltips + similar panel
    const recurringCheckboxes = document.querySelectorAll(".recurring-checkbox");
    recurringCheckboxes.forEach(cb => {
        cb.title = cb.checked ? "Recurring" : "Not Recurring";

        cb.addEventListener("change", function () {
            const txId = cb.getAttribute("data-tx-id");
            cb.title = cb.checked ? "Recurring" : "Not Recurring";
            if (!txId || txId === "new") return;
            showSimilarPanel(txId, groupMap, rowMeta);
        });
    });

    // Row menu (ellipsis) behavior
    const rowMenuButtons = document.querySelectorAll(".row-menu-btn");
    const editForm = document.getElementById("edit-transactions-form");

    rowMenuButtons.forEach(btn => {
        btn.addEventListener("click", function (e) {
            e.stopPropagation();
            const cell = btn.closest("td");
            const menu = cell.querySelector(".row-menu");
            if (!menu) return;

            // Close others
            document.querySelectorAll(".row-menu").forEach(m => {
                if (m !== menu) m.style.display = "none";
            });

            // Position and toggle this menu
            const rect = btn.getBoundingClientRect();
            menu.style.left = (rect.left - cell.getBoundingClientRect().left) + "px";
            menu.style.display = (menu.style.display === "none" || menu.style.display === "") ? "block" : "none";
        });
    });

    // Clicking outside closes menus
    document.addEventListener("click", function () {
        document.querySelectorAll(".row-menu").forEach(m => {
            m.style.display = "none";
        });
    });

    // Row-menu Save: submit full edit form
    const rowMenuSaveButtons = document.querySelectorAll(".row-menu-save");
    rowMenuSaveButtons.forEach(btn => {
        btn.addEventListener("click", function () {
            if (editForm) {
                editForm.submit();
            }
        });
    });
});