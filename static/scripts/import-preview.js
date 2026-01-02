document.addEventListener("DOMContentLoaded", function () {
    const uploadForm = document.getElementById("upload-form");
    const uploadPreviewBtn = document.getElementById("upload-preview-btn");
    const fileInput = document.getElementById("file");
    const importPreviewDialog = document.getElementById("import-preview-dialog");
    const importPreviewClose = document.getElementById("import-preview-close");
    const importCancelBtn = document.getElementById("import-cancel-btn");
    const importConfirmBtn = document.getElementById("import-confirm-btn");
    const importPreviewTbody = document.getElementById("import-preview-tbody");
    const importCount = document.getElementById("import-count");

    let previewData = [];

    // Preview import
    if (uploadPreviewBtn) {
        uploadPreviewBtn.addEventListener("click", function () {
            if (!fileInput.files || !fileInput.files[0]) {
                alert("Please select a file to upload");
                return;
            }

            const formData = new FormData();
            formData.append("action", "upload_preview");
            formData.append("file", fileInput.files[0]);

            fetch(window.location.href, {
                method: "POST",
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    previewData = data.preview;
                    displayImportPreview(data.preview);
                    importPreviewDialog.style.display = "flex";
                } else {
                    alert("Error: " + (data.error || "Unknown error"));
                }
            })
            .catch(error => {
                console.error("Preview error:", error);
                alert("Error previewing import");
            });
        });
    }

    // Close dialog
    function closeImportPreview() {
        importPreviewDialog.style.display = "none";
        previewData = [];
        fileInput.value = "";
    }

    if (importPreviewClose) {
        importPreviewClose.addEventListener("click", closeImportPreview);
    }

    if (importCancelBtn) {
        importCancelBtn.addEventListener("click", closeImportPreview);
    }

    importPreviewDialog?.addEventListener("click", function (e) {
        if (e.target === importPreviewDialog) {
            closeImportPreview();
        }
    });

    // Display preview
    function displayImportPreview(preview) {
        importPreviewTbody.innerHTML = "";
        importCount.textContent = preview.length;

        if (preview.length === 0) {
            importPreviewTbody.innerHTML = '<tr><td colspan="8" class="no-data">No transactions to import</td></tr>';
            return;
        }

        preview.forEach((tx, index) => {
            const row = document.createElement("tr");
            if (tx.has_match) {
                row.classList.add("has-match");
            }

            const txId = `import_${index}`;
            const matchIndicator = tx.has_match ? '<span class="match-indicator">●</span>' : '';

            row.innerHTML = `
                <td>${matchIndicator}${tx.date_raw}</td>
                <td title="${tx.description}">${truncate(tx.description, 30)}</td>
                <td>$${Math.abs(parseFloat(tx.amount)).toFixed(2)}</td>
                <td>
                    <input type="text" 
                           class="import-field" 
                           data-index="${index}"
                           data-field="custom_description"
                           value="${tx.custom_description || ''}" 
                           placeholder="Custom desc">
                </td>
                <td>
                    <select class="import-field category-type-input" 
                            data-index="${index}"
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
                    <select class="import-field parent-category-input" 
                            data-index="${index}"
                            data-field="parent_category"
                            data-tx-id="${txId}"
                            data-current="${tx.parent_category || ''}">
                        <option value=""></option>
                    </select>
                </td>
                <td>
                    <select class="import-field sub-category-input" 
                            data-index="${index}"
                            data-field="sub_category"
                            data-tx-id="${txId}"
                            data-current="${tx.sub_category || ''}">
                        <option value=""></option>
                    </select>
                </td>
                <td>
                    <input type="checkbox" 
                           class="import-field" 
                           data-index="${index}"
                           data-field="is_recurring"
                           ${tx.is_recurring ? 'checked' : ''}>
                </td>
            `;

            importPreviewTbody.appendChild(row);

            // Initialize category dropdowns
            initCategoryRow(txId);

            // Add change listeners
            const fields = row.querySelectorAll(".import-field");
            fields.forEach(field => {
                field.addEventListener("change", function () {
                    updatePreviewData(field);
                });
            });
        });
    }

    function updatePreviewData(field) {
        const index = parseInt(field.getAttribute("data-index"));
        const fieldName = field.getAttribute("data-field");
        const value = field.type === 'checkbox' ? (field.checked ? 1 : 0) : field.value;

        if (previewData[index]) {
            previewData[index][fieldName] = value;
        }
    }

    function truncate(str, maxLength) {
        if (str.length <= maxLength) return str;
        return str.substring(0, maxLength) + '...';
    }

    // Confirm import
    if (importConfirmBtn) {
        importConfirmBtn.addEventListener("click", function () {
            if (previewData.length === 0) {
                alert("No transactions to import");
                return;
            }

            const formData = new FormData();
            formData.append("action", "confirm_import");
            formData.append("import_data", JSON.stringify(previewData));

            fetch(window.location.href, {
                method: "POST",
                body: formData
            })
            .then(response => {
                if (response.ok) {
                    window.location.reload();
                } else {
                    return response.json().then(data => {
                        throw new Error(data.error || "Unknown error");
                    });
                }
            })
            .catch(error => {
                console.error("Import error:", error);
                alert("Error importing transactions: " + error.message);
            });
        });
    }
});