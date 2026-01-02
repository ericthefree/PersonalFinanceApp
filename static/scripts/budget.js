document.addEventListener("DOMContentLoaded", function () {
    const addBudgetItemBtn = document.getElementById("add-budget-item-btn");
    const importRecurringBtn = document.getElementById("import-recurring-btn");
    const dialog = document.getElementById("budget-item-dialog");
    const dialogClose = dialog?.querySelector(".dialog-close");
    const cancelBtn = dialog?.querySelector(".btn-cancel");
    const budgetForm = document.getElementById("budget-item-form");
    const frequencySelect = document.getElementById("budget_frequency");
    const nextDueField = document.getElementById("next-due-field");

    // Initialize category dropdowns
    initCategoryRow("budget");

    // Open dialog for adding new item
    if (addBudgetItemBtn) {
        addBudgetItemBtn.addEventListener("click", function () {
            openDialog("add");
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

    // Edit buttons
    const editButtons = document.querySelectorAll(".btn-edit");
    editButtons.forEach(btn => {
        btn.addEventListener("click", function () {
            const itemId = btn.getAttribute("data-item-id");
            openDialog("edit", itemId);
        });
    });

    // Delete buttons
    const deleteButtons = document.querySelectorAll(".btn-delete");
    deleteButtons.forEach(btn => {
        btn.addEventListener("click", function () {
            const itemId = btn.getAttribute("data-item-id");
            if (confirm("Are you sure you want to delete this budget item?")) {
                document.getElementById("delete-item-id").value = itemId;
                document.getElementById("delete-item-form").submit();
            }
        });
    });

    // Show/hide next due date based on frequency
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

    function openDialog(mode, itemId = null) {
        const dialogTitle = document.getElementById("dialog-title");
        const formAction = document.getElementById("form-action");
        const formItemId = document.getElementById("form-item-id");

        if (mode === "add") {
            dialogTitle.textContent = "Add Budget Item";
            formAction.value = "add_item";
            budgetForm.reset();
            formItemId.value = "";
            nextDueField.style.display = "none";
        } else if (mode === "edit" && itemId) {
            dialogTitle.textContent = "Edit Budget Item";
            formAction.value = "update_item";
            formItemId.value = itemId;
            loadItemData(itemId);
        }

        dialog.style.display = "flex";
    }

    function closeDialog() {
        dialog.style.display = "none";
        budgetForm.reset();
    }

    function loadItemData(itemId) {
        // Find the row with this item
        const row = document.querySelector(`button[data-item-id="${itemId}"]`)?.closest("tr");
        if (!row) return;

        const cells = row.querySelectorAll("td");

        // Populate form fields
        document.getElementById("budget_day").value = cells[0].textContent.trim();
        document.getElementById("budget_description").value = cells[1].textContent.trim();

        // Parse amount (remove currency formatting)
        const amountText = cells[2].textContent.trim().replace(/[$,]/g, '');
        document.getElementById("budget_amount").value = amountText;

        // Set frequency
        const frequency = cells[3].textContent.trim().toLowerCase();
        document.getElementById("budget_frequency").value = frequency;

        // Show/hide next due date field
        if (frequency !== "monthly") {
            nextDueField.style.display = "flex";
            const nextDue = cells[4].textContent.trim();
            if (nextDue !== "-") {
                document.getElementById("budget_next_due").value = nextDue;
            }
        }

        // Category would need to be parsed from cells[5]
        // This is simplified - you may want to store more data attributes
    }
});