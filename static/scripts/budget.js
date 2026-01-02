document.addEventListener("DOMContentLoaded", function () {
    const addBudgetItemBtn = document.getElementById("add-budget-item-btn");
    const importRecurringBtn = document.getElementById("import-recurring-btn");
    const dialog = document.getElementById("budget-item-dialog");
    const dialogClose = dialog?.querySelector(".dialog-close");
    const cancelBtn = dialog?.querySelector(".btn-cancel");
    const budgetForm = document.getElementById("budget-item-form");
    const frequencySelect = document.getElementById("budget_frequency");
    const nextDueField = document.getElementById("next-due-field");
    const budgetEditForm = document.getElementById("budget-edit-form");

    // Initialize category dropdowns for dialog
    initCategoryRow("new_budget");

    // Initialize category dropdowns for all budget items
    const budgetRows = document.querySelectorAll(".budget-row");
    budgetRows.forEach(row => {
        const itemId = row.getAttribute("data-item-id");
        if (itemId) {
            initCategoryRow(`budget_${itemId}`);
        }
    });

    // Frequency change listeners to show/hide next due date
    const frequencySelects = document.querySelectorAll(".frequency-select");
    frequencySelects.forEach(select => {
        select.addEventListener("change", function() {
            const itemId = this.getAttribute("data-item-id");
            const nextDueInput = document.querySelector(`.next-due-input[data-item-id="${itemId}"]`);
            const monthlyIndicator = this.closest("tr").querySelector(".monthly-indicator");

            if (this.value === "monthly") {
                if (nextDueInput) nextDueInput.style.display = "none";
                if (monthlyIndicator) monthlyIndicator.style.display = "inline";
            } else {
                if (nextDueInput) nextDueInput.style.display = "block";
                if (monthlyIndicator) monthlyIndicator.style.display = "none";
            }
        });
    });

    // Row menu behavior
    const rowMenuButtons = document.querySelectorAll(".row-menu-btn");

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

            // Position menu relative to viewport
            const btnRect = btn.getBoundingClientRect();
            menu.style.position = "fixed";
            menu.style.left = (btnRect.right + 5) + "px";
            menu.style.top = btnRect.top + "px";

            // Toggle display
            menu.style.display = (menu.style.display === "none" || menu.style.display === "") ? "block" : "none";
        });
    });

    // Prevent clicks inside menus from closing them
    const rowMenus = document.querySelectorAll(".row-menu");
    rowMenus.forEach(menu => {
        menu.addEventListener("click", function (e) {
            e.stopPropagation();
        });
    });

    // Clicking outside closes menus
    document.addEventListener("click", function (e) {
        if (!e.target.closest(".row-menu")) {
            document.querySelectorAll(".row-menu").forEach(m => {
                m.style.display = "none";
            });
        }
    });

    // Row-menu Save: submit full edit form
    const rowMenuSaveButtons = document.querySelectorAll(".row-menu-save");
    rowMenuSaveButtons.forEach(btn => {
        btn.addEventListener("click", function () {
            if (budgetEditForm) {
                budgetEditForm.submit();
            }
        });
    });

    // Delete buttons
    const deleteButtons = document.querySelectorAll(".row-menu-delete");
    deleteButtons.forEach(btn => {
        btn.addEventListener("click", function () {
            const itemId = btn.getAttribute("data-item-id");
            if (confirm("Are you sure you want to delete this budget item?")) {
                document.getElementById("delete-item-id").value = itemId;
                document.getElementById("delete-item-form").submit();
            }
        });
    });

    // Open dialog for adding new item
    if (addBudgetItemBtn) {
        addBudgetItemBtn.addEventListener("click", function () {
            openDialog();
        });
    }

    // Import recurring transactions
    if (importRecurringBtn) {
        importRecurringBtn.addEventListener("click", function () {
            if (confirm("Import recurring transactions from last month to budget?")) {
                document.getElementById("import-recurring-form").submit();
            }
        });
    }

    // Show/hide next due date based on frequency in dialog
    if (frequencySelect) {
        frequencySelect.addEventListener("change", function () {
            if (this.value === "monthly") {
                nextDueField.style.display = "none";
                document.getElementById("budget_next_due").required = false;
            } else {
                nextDueField.style.display = "flex";
                document.getElementById("budget_next_due").required = true;
            }
        });
    }

    // Close dialog
    if (dialogClose) {
        dialogClose.addEventListener("click", closeDialog);
    }

    if (cancelBtn) {
        cancelBtn.addEventListener("click", closeDialog);
    }

    if (dialog) {
        dialog.addEventListener("click", function (e) {
            if (e.target === dialog) {
                closeDialog();
            }
        });
    }

    function openDialog() {
        budgetForm.reset();
        nextDueField.style.display = "none";
        dialog.style.display = "flex";
    }

    function closeDialog() {
        dialog.style.display = "none";
        budgetForm.reset();
    }
});