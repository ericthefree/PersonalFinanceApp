function updateFieldTooltip(element) {
    if (element.tagName === 'SELECT') {
        const selectedOption = element.options[element.selectedIndex];
        element.title = selectedOption ? selectedOption.text : "";
    } else if (element.tagName === 'INPUT') {
        element.title = element.value || "";
    }
}

function buildSimilarGroups() {
    /**
     * Build a map of similar transactions based on:
     * - Similar description (exact match)
     * - Amount within ±5
     * - Day within ±2 days but in different months
     */
    const allRows = document.querySelectorAll(".transaction-row");
    const groupMap = {}; // txId -> array of similar txIds
    const rowMeta = {};  // txId -> { description, amount, date, day, month, year }

    // First pass: collect metadata for all transactions
    allRows.forEach(row => {
        const txId = row.getAttribute("data-tx-id");
        const description = row.getAttribute("data-description") || "";
        const amountStr = row.getAttribute("data-amount") || "0";
        const dateStr = row.getAttribute("data-date") || "";

        const amount = parseFloat(amountStr);

        // Parse date to get day, month, year
        let day = null, month = null, year = null;
        if (dateStr) {
            const dateParts = parseDateDisplay(dateStr);
            if (dateParts) {
                day = dateParts.day;
                month = dateParts.month;
                year = dateParts.year;
            }
        }

        rowMeta[txId] = {
            description: description.toLowerCase().trim(),
            amount: amount,
            date: dateStr,
            day: day,
            month: month,
            year: year
        };
    });

    // Second pass: find similar transactions for each row
    Object.keys(rowMeta).forEach(txId => {
        const current = rowMeta[txId];
        const similarIds = [];

        Object.keys(rowMeta).forEach(otherTxId => {
            if (txId === otherTxId) return; // Skip self

            const other = rowMeta[otherTxId];

            // Check criteria:
            // 1. Same description (case-insensitive)
            const sameDescription = current.description === other.description;

            // 2. Amount within ±5
            const amountDiff = Math.abs(current.amount - other.amount);
            const similarAmount = amountDiff <= 5;

            // 3. Day within ±2 days AND different month
            let similarDay = false;
            if (current.day !== null && other.day !== null) {
                const dayDiff = Math.abs(current.day - other.day);
                const differentMonth = current.month !== other.month || current.year !== other.year;
                similarDay = dayDiff <= 2 && differentMonth;
            }

            // Must match all criteria
            if (sameDescription && similarAmount && similarDay) {
                similarIds.push(otherTxId);
            }
        });

        groupMap[txId] = similarIds;
    });

    return { groupMap, rowMeta };
}

function parseDateDisplay(dateStr) {
    /**
     * Parse date from display format "10-Nov-25" to extract day, month, year
     * Returns { day: number, month: number (0-11), year: number } or null
     */
    if (!dateStr) return null;

    // Try format: "10-Nov-25"
    const match1 = dateStr.match(/^(\d{1,2})-([A-Za-z]{3})-(\d{2})$/);
    if (match1) {
        const day = parseInt(match1[1], 10);
        const monthStr = match1[2].toLowerCase();
        const year = 2000 + parseInt(match1[3], 10);

        const months = {
            'jan': 0, 'feb': 1, 'mar': 2, 'apr': 3, 'may': 4, 'jun': 5,
            'jul': 6, 'aug': 7, 'sep': 8, 'oct': 9, 'nov': 10, 'dec': 11
        };

        const month = months[monthStr];
        if (month !== undefined) {
            return { day, month, year };
        }
    }

    // Try format: "11/10/2025" or "11/10/25"
    const match2 = dateStr.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/);
    if (match2) {
        const month = parseInt(match2[1], 10) - 1; // 0-indexed
        const day = parseInt(match2[2], 10);
        let year = parseInt(match2[3], 10);
        if (year < 100) year += 2000;
        return { day, month, year };
    }

    return null;
}

function showSimilarPanel(txId, groupMap, rowMeta) {
    const panel = document.querySelector(`.similar-panel[data-tx-id="${txId}"]`);
    if (!panel) return;

    const similarIds = groupMap[txId] || [];

    if (similarIds.length === 0) {
        panel.style.display = "none";
        panel.innerHTML = "";
        document.getElementById(`propagate-to-${txId}`).value = "";
        return;
    }

    // Build the panel HTML
    let html = `<div class="similar-header">Found ${similarIds.length} similar transaction(s):</div>`;
    html += '<div class="similar-checkboxes">';

    similarIds.forEach(simId => {
        const meta = rowMeta[simId];
        const amountStr = meta.amount >= 0 ? `+$${meta.amount.toFixed(2)}` : `-$${Math.abs(meta.amount).toFixed(2)}`;

        html += `
            <label class="similar-item">
                <input type="checkbox" 
                       class="similar-checkbox" 
                       data-target-id="${simId}"
                       data-source-id="${txId}"
                       checked>
                <span>${meta.date} - ${meta.description.substring(0, 30)} - ${amountStr}</span>
            </label>
        `;
    });

    html += '</div>';
    html += '<div class="similar-note">Changes will apply to checked transactions</div>';

    panel.innerHTML = html;
    panel.style.display = "block";

    // Update hidden propagate_to field when checkboxes change
    updatePropagateField(txId);

    const checkboxes = panel.querySelectorAll(".similar-checkbox");
    checkboxes.forEach(cb => {
        cb.addEventListener("change", function() {
            updatePropagateField(txId);
        });
    });
}

function updatePropagateField(txId) {
    const panel = document.querySelector(`.similar-panel[data-tx-id="${txId}"]`);
    if (!panel) return;

    const checkedBoxes = panel.querySelectorAll(".similar-checkbox:checked");
    const selectedIds = Array.from(checkedBoxes).map(cb => cb.getAttribute("data-target-id"));

    const hiddenField = document.getElementById(`propagate-to-${txId}`);
    if (hiddenField) {
        hiddenField.value = selectedIds.join(",");
    }
}

document.addEventListener("DOMContentLoaded", function () {
    // Delete button handler
    const deleteButtons = document.querySelectorAll(".row-menu-delete");
    deleteButtons.forEach(btn => {
        btn.addEventListener("click", function () {
            const txId = btn.getAttribute("data-tx-id");
            const confirmed = confirm("Are you sure you want to delete this transaction?");

            if (confirmed) {
                const formData = new FormData();
                formData.append("action", "delete_tx");
                formData.append("tx_id", txId);

                fetch(window.location.href, {
                    method: "POST",
                    body: formData
                })
                .then(response => {
                    if (response.ok) {
                        window.location.reload();
                    } else {
                        alert("Error deleting transaction");
                    }
                })
                .catch(error => {
                    console.error("Delete error:", error);
                    alert("Error deleting transaction");
                });
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

            // Position menu relative to viewport
            const btnRect = btn.getBoundingClientRect();

            menu.style.position = "fixed";
            menu.style.left = (btnRect.right + 5) + "px"; // 5px to the right of button
            menu.style.top = btnRect.top + "px"; // Aligned with button

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
        // Only close if not clicking inside a menu
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
            if (editForm) {
                editForm.submit();
            }
        });
    });

    // Add Transaction Dialog
    const openDialogBtn = document.getElementById("open-add-tx-dialog");
    const dialog = document.getElementById("add-tx-dialog");
    const closeDialogBtn = dialog?.querySelector(".dialog-close");
    const cancelBtn = dialog?.querySelector(".btn-cancel");
    const addTxForm = document.getElementById("add-tx-form");
    const addAnotherCheckbox = document.getElementById("add_another_checkbox");
    const addAnotherHidden = document.getElementById("add_another_hidden");

    // Open dialog
    if (openDialogBtn) {
        openDialogBtn.addEventListener("click", function () {
            dialog.style.display = "flex";
        });
    }

    // Close dialog function
    function closeDialog() {
        dialog.style.display = "none";
        clearAddTxForm();
    }

    // Clear form fields
    function clearAddTxForm() {
        document.getElementById("new_date").value = "";
        document.getElementById("new_description").value = "";
        document.getElementById("new_custom_description").value = "";
        document.getElementById("new_amount").value = "";
        document.getElementById("new_category_type").value = "";
        document.getElementById("new_parent_category").value = "";
        document.getElementById("new_sub_category").value = "";
        document.getElementById("new_is_recurring").checked = false;
        addAnotherCheckbox.checked = false;

        // Clear message
        const messageDiv = document.getElementById("add-tx-message");
        if (messageDiv) {
            messageDiv.style.display = "none";
            messageDiv.className = "form-message";
        }
    }

    // Close dialog on X button
    if (closeDialogBtn) {
        closeDialogBtn.addEventListener("click", closeDialog);
    }

    // Close dialog on Cancel button
    if (cancelBtn) {
        cancelBtn.addEventListener("click", closeDialog);
    }

    // Close dialog when clicking outside
    if (dialog) {
        dialog.addEventListener("click", function (e) {
            if (e.target === dialog) {
                closeDialog();
            }
        });
    }

    // Handle form submission
    if (addTxForm) {
        addTxForm.addEventListener("submit", function (e) {
            const messageDiv = document.getElementById("add-tx-message");

            // Hide any existing message
            messageDiv.style.display = "none";
            messageDiv.className = "form-message";

            // Set the hidden field based on checkbox
            addAnotherHidden.value = addAnotherCheckbox.checked ? "1" : "0";

            // If "add another" is NOT checked, the form will submit normally and redirect
            // If "add another" IS checked, we'll handle it via AJAX
            if (addAnotherCheckbox.checked) {
                e.preventDefault();

                const formData = new FormData(addTxForm);

                fetch(window.location.href, {
                    method: "POST",
                    body: formData
                })
                .then(response => {
                    if (response.ok) {
                        // Clear form but keep dialog open
                        clearAddTxForm();

                        // Show success message
                        messageDiv.textContent = "Transaction added successfully!";
                        messageDiv.className = "form-message success";
                        messageDiv.style.display = "block";

                        // Auto-hide message after 3 seconds
                        setTimeout(() => {
                            messageDiv.style.display = "none";
                        }, 3000);
                    } else {
                        // Show error message
                        messageDiv.textContent = "Error adding transaction. Please check your input.";
                        messageDiv.className = "form-message error";
                        messageDiv.style.display = "block";
                    }
                })
                .catch(error => {
                    console.error("Error:", error);

                    // Show error message
                    messageDiv.textContent = "Network error. Please try again.";
                    messageDiv.className = "form-message error";
                    messageDiv.style.display = "block";
                });
            }
            // If checkbox not checked, form submits normally and page redirects
        });
    }
});