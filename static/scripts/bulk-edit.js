document.addEventListener("DOMContentLoaded", function () {
    const openBulkEditBtn = document.getElementById("open-bulk-edit-btn");
    const bulkEditDialog = document.getElementById("bulk-edit-dialog");
    const bulkEditClose = document.getElementById("bulk-edit-close");
    const searchBtn = document.getElementById("search-btn");
    const clearSearchBtn = document.getElementById("clear-search-btn");
    const bulkSaveBtn = document.getElementById("bulk-save-btn");
    const selectAllCheckbox = document.getElementById("select-all-checkbox");
    const resultsSection = document.getElementById("results-section");
    const resultsTbody = document.getElementById("results-tbody");
    const resultsCount = document.getElementById("results-count");

    let searchResults = [];

    // Initialize category dropdowns for search
    initCategoryRow("search");

    // Open dialog
    if (openBulkEditBtn) {
        openBulkEditBtn.addEventListener("click", function () {
            bulkEditDialog.style.display = "flex";
        });
    }

    // Close dialog
    function closeDialog() {
        bulkEditDialog.style.display = "none";
        clearSearch();
    }

    if (bulkEditClose) {
        bulkEditClose.addEventListener("click", closeDialog);
    }

    bulkEditDialog?.addEventListener("click", function (e) {
        if (e.target === bulkEditDialog) {
            closeDialog();
        }
    });

    // Search transactions
    if (searchBtn) {
        searchBtn.addEventListener("click", performSearch);
    }

    // Clear search
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener("click", clearSearch);
    }

    // Select all checkbox
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener("change", function () {
            const checkboxes = resultsTbody.querySelectorAll('.tx-checkbox');
            checkboxes.forEach(cb => {
                cb.checked = selectAllCheckbox.checked;
                updateRowSelection(cb);
            });
        });
    }

    // Save bulk changes
    if (bulkSaveBtn) {
        bulkSaveBtn.addEventListener("click", saveBulkChanges);
    }

    function performSearch() {
        const formData = new FormData();
        formData.append("action", "bulk_search");
        formData.append("search_description", document.getElementById("search_description").value);
        formData.append("search_amount", document.getElementById("search_amount").value);
        formData.append("search_category_type", document.getElementById("search_category_type").value);
        formData.append("search_parent_category", document.getElementById("search_parent_category").value);
        formData.append("search_sub_category", document.getElementById("search_sub_category").value);
        formData.append("search_exact_amount", document.getElementById("search_exact_amount").checked ? "1" : "0");
        formData.append("search_uncategorized", document.getElementById("search_uncategorized").checked ? "1" : "0");

        fetch(window.location.href, {
            method: "POST",
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            searchResults = data;
            displayResults(data);
        })
        .catch(error => {
            console.error("Search error:", error);
            alert("Error performing search");
        });
    }

    function displayResults(results) {
        resultsTbody.innerHTML = "";
        resultsCount.textContent = results.length;

        if (results.length === 0) {
            resultsTbody.innerHTML = '<tr><td colspan="9" class="no-data">No transactions found</td></tr>';
            resultsSection.style.display = "block";
            return;
        }

        results.forEach((tx, index) => {
            const row = document.createElement("tr");
            row.setAttribute("data-tx-id", tx.id);

            const txId = `bulk_${tx.id}`;

            row.innerHTML = `
                <td class="select-col">
                    <input type="checkbox" class="tx-checkbox" value="${tx.id}">
                </td>
                <td>${tx.date_display || ''}</td>
                <td title="${tx.description || ''}">${truncate(tx.description || '', 30)}</td>
                <td>
                    <input type="text" 
                           class="edit-field custom-desc-field" 
                           data-field="custom_description"
                           value="${tx.custom_description || ''}" 
                           placeholder="Custom desc">
                </td>
                <td>$${Math.abs(tx.amount).toFixed(2)}</td>
                <td>
                    <select class="edit-field category-type-input" 
                            data-field="category_type"
                            data-tx-id="${txId}"
                            data-current-parent="${tx.parent_category || ''}"
                            data-current-sub="${tx.sub_category || ''}">
                        <option value=""></option>
                        <option value="Income" ${tx.category_type === 'Income' ? 'selected' : ''}>Income</option>
                        <option value="Bills" ${tx.category_type === 'Bills' ? 'selected' : ''}>Bills</option>
                        <option value="Expenses" ${tx.category_type === 'Expenses' ? 'selected' : ''}>Expenses</option>
                        <option value="Debts" ${tx.category_type === 'Debts' ? 'selected' : ''}>Debts</option>
                        <option value="Investments" ${tx.category_type === 'Investments' ? 'selected' : ''}>Investments</option>
                        <option value="Transfers" ${tx.category_type === 'Transfers' ? 'selected' : ''}>Transfers</option>
                    </select>
                </td>
                <td>
                    <select class="edit-field parent-category-input" 
                            data-field="parent_category"
                            data-tx-id="${txId}"
                            data-current="${tx.parent_category || ''}">
                        <option value=""></option>
                    </select>
                </td>
                <td>
                    <select class="edit-field sub-category-input" 
                            data-field="sub_category"
                            data-tx-id="${txId}"
                            data-current="${tx.sub_category || ''}">
                        <option value=""></option>
                    </select>
                </td>
                <td>
                    <input type="checkbox" 
                           class="edit-field recurring-check" 
                           data-field="is_recurring"
                           ${tx.is_recurring ? 'checked' : ''}>
                </td>
            `;

            resultsTbody.appendChild(row);

            // Initialize category dropdowns for this row
            initCategoryRow(txId);

            // Add checkbox listener
            const checkbox = row.querySelector(".tx-checkbox");
            checkbox.addEventListener("change", function () {
                updateRowSelection(checkbox);
            });

            // Add edit field listeners for inline editing
            const editFields = row.querySelectorAll(".edit-field");
            editFields.forEach(field => {
                if (field.type === 'checkbox') {
                    field.addEventListener("change", function () {
                        propagateToCheckedRows(field);
                    });
                } else {
                    field.addEventListener("input", function () {
                        propagateToCheckedRows(field);
                    });
                    field.addEventListener("change", function () {
                        propagateToCheckedRows(field);
                    });
                }
            });
        });

        resultsSection.style.display = "block";
        selectAllCheckbox.checked = false;
    }

    function truncate(str, maxLength) {
        if (str.length <= maxLength) return str;
        return str.substring(0, maxLength) + '...';
    }

    function updateRowSelection(checkbox) {
        const row = checkbox.closest("tr");
        if (checkbox.checked) {
            row.classList.add("selected");
        } else {
            row.classList.remove("selected");
        }
    }

    function propagateToCheckedRows(sourceField) {
        const fieldName = sourceField.getAttribute("data-field");
        const newValue = sourceField.type === 'checkbox' ? sourceField.checked : sourceField.value;

        // Find all checked rows
        const checkedRows = resultsTbody.querySelectorAll("tr.selected");

        checkedRows.forEach(row => {
            const targetField = row.querySelector(`[data-field="${fieldName}"]`);
            if (targetField && targetField !== sourceField) {
                if (targetField.type === 'checkbox') {
                    targetField.checked = newValue;
                } else {
                    targetField.value = newValue;

                    // If it's a category type, update dependent dropdowns
                    if (fieldName === 'category_type') {
                        const txId = targetField.getAttribute("data-tx-id");
                        const parentSelect = row.querySelector(`.parent-category-input[data-tx-id="${txId}"]`);
                        const subSelect = row.querySelector(`.sub-category-input[data-tx-id="${txId}"]`);

                        if (parentSelect && subSelect) {
                            parentSelect.value = "";
                            subSelect.value = "";
                            populateParentOptions(newValue, parentSelect, "");
                            populateSubOptions(newValue, "", subSelect, "");
                        }
                    } else if (fieldName === 'parent_category') {
                        const txId = targetField.getAttribute("data-tx-id");
                        const typeSelect = row.querySelector(`.category-type-input[data-tx-id="${txId}"]`);
                        const subSelect = row.querySelector(`.sub-category-input[data-tx-id="${txId}"]`);

                        if (typeSelect && subSelect) {
                            subSelect.value = "";
                            populateSubOptions(typeSelect.value, newValue, subSelect, "");
                        }
                    }
                }
            }
        });
    }

    function clearSearch() {
        document.getElementById("search_description").value = "";
        document.getElementById("search_amount").value = "";
        document.getElementById("search_category_type").value = "";
        document.getElementById("search_parent_category").value = "";
        document.getElementById("search_sub_category").value = "";
        document.getElementById("search_exact_amount").checked = false;
        document.getElementById("search_uncategorized").checked = false;

        resultsTbody.innerHTML = "";
        resultsSection.style.display = "none";
        searchResults = [];
    }

    function saveBulkChanges() {
        const selectedRows = resultsTbody.querySelectorAll("tr.selected");

        if (selectedRows.length === 0) {
            alert("Please select at least one transaction to update");
            return;
        }

        // Collect updates from each selected row
        const updates = [];
        selectedRows.forEach(row => {
            const txId = row.getAttribute("data-tx-id");
            const customDesc = row.querySelector('[data-field="custom_description"]').value;
            const categoryType = row.querySelector('[data-field="category_type"]').value;
            const parentCategory = row.querySelector('[data-field="parent_category"]').value;
            const subCategory = row.querySelector('[data-field="sub_category"]').value;
            const isRecurring = row.querySelector('[data-field="is_recurring"]').checked;

            updates.push({
                id: txId,
                custom_description: customDesc || '',
                category_type: categoryType || '',
                parent_category: parentCategory || '',
                sub_category: subCategory || '',
                is_recurring: isRecurring ? '1' : '0'
            });
        });

        // Send all updates
        const formData = new FormData();
        formData.append("action", "bulk_update");

        updates.forEach(update => {
            formData.append("selected_ids[]", update.id);
        });

        // Use the first selected row's values for bulk update
        const firstUpdate = updates[0];
        formData.append("bulk_custom_description", firstUpdate.custom_description);
        formData.append("bulk_category_type", firstUpdate.category_type);
        formData.append("bulk_parent_category", firstUpdate.parent_category);
        formData.append("bulk_sub_category", firstUpdate.sub_category);
        formData.append("bulk_is_recurring", firstUpdate.is_recurring);

        fetch(window.location.href, {
            method: "POST",
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                closeDialog();
                window.location.reload();
            } else {
                alert("Error: " + (data.error || "Unknown error"));
            }
        })
        .catch(error => {
            console.error("Save error:", error);
            alert("Error saving changes");
        });
    }
});