const API_BASE_URL_FALLBACK = window.AUDIT_CONFIG.API_BASE_URL;
const dashboardState = {
    files: [],
    selectedUpdateFileId: ""
};

function getAuditApp() {
    return window.AuditApp || {};
}

function readUserId() {
    const appUserId = getAuditApp().userId?.();
    if (appUserId) {
        return appUserId;
    }

    try {
        const storedUser = JSON.parse(localStorage.getItem("auditUser") || "null");
        const user = storedUser?.user || storedUser;
        return user?.account_id || user?.user_id || user?.id || "";
    } catch (error) {
        return "";
    }
}

function escapeHtml(value) {
    const escape = getAuditApp().escapeHtml;
    if (escape) {
        return escape(value);
    }

    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatSize(size) {
    const format = getAuditApp().formatSize;
    if (format) {
        return format(size);
    }

    if (size < 1024) {
        return `${size} B`;
    }
    if (size < 1024 * 1024) {
        return `${(size / 1024).toFixed(1)} KB`;
    }
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function makeKeywordPills(keywords = []) {
    const makePills = getAuditApp().makeKeywordPills;
    if (makePills) {
        return makePills(keywords);
    }

    return keywords.map((keyword) => `<span class="keyword-pill">${escapeHtml(keyword)}</span>`).join("");
}

function plainFileUrl(fileId, disposition = "inline") {
    const currentUserId = readUserId();
    const params = new URLSearchParams({
        user_id: currentUserId,
        disposition
    });
    return `${API_BASE_URL_FALLBACK}/home/files/${encodeURIComponent(fileId)}/plain?${params.toString()}`;
}

function makeFileActions(file) {
    if (file.audit_status === "missing") {
        return `<span class="muted-text">不可用</span>`;
    }

    const fileId = escapeHtml(file.file_id);
    const fileName = escapeHtml(file.file_name);
    return `
        <div class="file-actions">
            <button class="mini-button" type="button" data-file-action="preview" data-file-id="${fileId}" data-file-name="${fileName}">预览</button>
            <button class="mini-button" type="button" data-file-action="download" data-file-id="${fileId}" data-file-name="${fileName}">下载</button>
            <button class="mini-button danger-mini-button" type="button" data-file-action="delete" data-file-id="${fileId}" data-file-name="${fileName}">删除</button>
        </div>
    `;
}

function statusText(status) {
    const appStatusText = getAuditApp().statusText;
    if (appStatusText) {
        return appStatusText(status);
    }

    const statusMap = {
        pending: "未审计",
        complete: "完整",
        broken: "损坏",
        missing: "文件丢失"
    };
    return statusMap[status] || status || "未知";
}

function statusClass(status) {
    const appStatusClass = getAuditApp().statusClass;
    if (appStatusClass) {
        return appStatusClass(status);
    }

    if (status === "complete") {
        return "status-complete";
    }
    if (status === "broken" || status === "missing") {
        return "status-broken";
    }
    return "status-pending";
}

async function apiJson(path, options = {}) {
    const appApiJson = getAuditApp().apiJson;
    if (appApiJson) {
        return appApiJson(path, options);
    }

    const response = await fetch(`${API_BASE_URL_FALLBACK}${path}`, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "请求失败");
    }
    return data;
}

async function apiForm(path, formData) {
    const response = await fetch(`${API_BASE_URL_FALLBACK}${path}`, {
        method: "POST",
        body: formData
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        if (typeof data.detail === "string") {
            throw new Error(data.detail);
        }
        throw new Error("请求失败");
    }
    return data;
}

function renderSummary(dashboard) {
    document.getElementById("fileCount").textContent = dashboard.user_file_count;
    document.getElementById("integrityRatio").textContent = `${dashboard.integrity_ratio}%`;
    document.getElementById("keywordCount").textContent = dashboard.keyword_count;
    document.getElementById("latestAudit").textContent = dashboard.latest_audit_time || "暂无记录";
}

function renderFiles(files) {
    const fileTableBody = document.getElementById("fileTableBody");
    dashboardState.files = files;

    if (!files.length) {
        fileTableBody.innerHTML = `<tr class="empty-row"><td colspan="7">暂无文件</td></tr>`;
        return;
    }

    fileTableBody.innerHTML = files.map((file) => `
        <tr>
            <td><strong>${escapeHtml(file.file_name)}</strong><br><span>${escapeHtml(file.file_id)}</span></td>
            <td>${formatSize(file.file_size)}</td>
            <td>${escapeHtml(file.upload_time)}</td>
            <td>${makeKeywordPills(file.keywords || [])}</td>
            <td><span class="status-pill ${statusClass(file.audit_status)}">${escapeHtml(statusText(file.audit_status))}</span></td>
            <td>${escapeHtml(file.last_audit_time || "暂无记录")}</td>
            <td>${makeFileActions(file)}</td>
        </tr>
    `).join("");
}

function fallbackDownload(url, fileName) {
    const link = document.createElement("a");
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
}

async function downloadPlainFile(fileId, fileName) {
    const url = plainFileUrl(fileId, "attachment");

    if (!window.showSaveFilePicker) {
        fallbackDownload(url, fileName);
        return;
    }

    const handle = await window.showSaveFilePicker({
        suggestedName: fileName
    });
    const response = await fetch(url);
    if (!response.ok) {
        const message = await response.text();
        throw new Error(message || "下载失败");
    }

    const blob = await response.blob();
    const writable = await handle.createWritable();
    await writable.write(blob);
    await writable.close();
}

async function deleteFile(fileId) {
    const currentUserId = readUserId();
    if (!currentUserId) {
        throw new Error("请先登录");
    }

    await apiJson(`/home/files/${encodeURIComponent(fileId)}?user_id=${encodeURIComponent(currentUserId)}`, {
        method: "DELETE"
    });
}

function currentUpdateFile() {
    return dashboardState.files.find((file) => file.file_id === dashboardState.selectedUpdateFileId) || null;
}

function renderUpdateFileChoices() {
    const updateFileList = document.getElementById("updateFileList");
    if (!updateFileList) {
        return;
    }

    const availableFiles = dashboardState.files.filter((file) => file.audit_status !== "missing");
    if (!availableFiles.length) {
        updateFileList.innerHTML = `<div class="empty-row">暂无可更新文件</div>`;
        return;
    }

    updateFileList.innerHTML = availableFiles.map((file) => `
        <label class="update-file-choice">
            <input type="radio" name="updateFileChoice" value="${escapeHtml(file.file_id)}" ${file.file_id === dashboardState.selectedUpdateFileId ? "checked" : ""}>
            <div>
                <strong>${escapeHtml(file.file_name)}</strong>
                <span>${escapeHtml(file.file_id)}</span>
            </div>
            <span>${formatSize(file.file_size)}</span>
        </label>
    `).join("");
}

function showUpdateStep(stepName) {
    const selectStep = document.getElementById("updateSelectStep");
    const uploadStep = document.getElementById("updateUploadStep");
    selectStep?.classList.toggle("active", stepName === "select");
    uploadStep?.classList.toggle("active", stepName === "upload");
}

function resetUpdateUploadForm() {
    const updateFileInput = document.getElementById("updateFileInput");
    const updateFileInputName = document.getElementById("updateFileInputName");
    const updateUploadMessage = document.getElementById("updateUploadMessage");
    if (updateFileInput) {
        updateFileInput.value = "";
    }
    if (updateFileInputName) {
        updateFileInputName.textContent = "上传后将保留原文件 ID 和编号";
    }
    if (updateUploadMessage) {
        updateUploadMessage.textContent = "";
    }
}

function openUpdateModal() {
    const modal = document.getElementById("updateFileModal");
    const selectMessage = document.getElementById("updateSelectMessage");
    dashboardState.selectedUpdateFileId = "";
    if (selectMessage) {
        selectMessage.textContent = "";
    }
    resetUpdateUploadForm();
    renderUpdateFileChoices();
    showUpdateStep("select");
    modal?.classList.add("open");
    modal?.setAttribute("aria-hidden", "false");
}

function closeUpdateModal() {
    const modal = document.getElementById("updateFileModal");
    modal?.classList.remove("open");
    modal?.setAttribute("aria-hidden", "true");
}

function goToUpdateUploadStep() {
    const selectMessage = document.getElementById("updateSelectMessage");
    const selectedFile = currentUpdateFile();
    if (!selectedFile) {
        if (selectMessage) {
            selectMessage.textContent = "请先选择一个文件";
        }
        return;
    }

    const selectedUpdateFile = document.getElementById("selectedUpdateFile");
    const updateKeywordsInput = document.getElementById("updateKeywordsInput");
    if (selectedUpdateFile) {
        selectedUpdateFile.innerHTML = `
            <strong>${escapeHtml(selectedFile.file_name)}</strong>
            <span>${escapeHtml(selectedFile.file_id)}</span>
        `;
    }
    if (updateKeywordsInput) {
        updateKeywordsInput.value = (selectedFile.keywords || []).join(", ");
    }
    resetUpdateUploadForm();
    showUpdateStep("upload");
}

async function submitUpdateFile(event) {
    event.preventDefault();

    const selectedFile = currentUpdateFile();
    const updateFileInput = document.getElementById("updateFileInput");
    const updateKeywordsInput = document.getElementById("updateKeywordsInput");
    const updateUploadMessage = document.getElementById("updateUploadMessage");
    const submitButton = document.getElementById("submitUpdateFile");
    const currentUserId = readUserId();

    if (!selectedFile) {
        updateUploadMessage.textContent = "请先选择一个文件";
        showUpdateStep("select");
        return;
    }
    if (!updateFileInput?.files?.length) {
        updateUploadMessage.textContent = "请选择替换文件";
        return;
    }
    if (!updateKeywordsInput.value.trim()) {
        updateUploadMessage.textContent = "请填写关键词";
        return;
    }
    if (!currentUserId) {
        updateUploadMessage.textContent = "请先登录";
        return;
    }

    const formData = new FormData();
    formData.append("user_id", currentUserId);
    formData.append("file", updateFileInput.files[0]);
    formData.append("keywords", updateKeywordsInput.value);

    const originalText = submitButton.textContent;
    submitButton.disabled = true;
    submitButton.textContent = "更新中...";
    updateUploadMessage.textContent = "";
    try {
        await apiForm(`/home/files/${encodeURIComponent(selectedFile.file_id)}/update`, formData);
        closeUpdateModal();
        await loadDashboard();
        window.alert("文件更新成功");
    } catch (error) {
        updateUploadMessage.textContent = error.message || "更新失败";
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = originalText;
    }
}

function bindFileActions() {
    const fileTableBody = document.getElementById("fileTableBody");
    fileTableBody?.addEventListener("click", async (event) => {
        const button = event.target.closest("[data-file-action]");
        if (!button) {
            return;
        }

        const { fileAction, fileId, fileName } = button.dataset;
        if (fileAction === "preview") {
            window.open(plainFileUrl(fileId, "inline"), "_blank", "noopener");
            return;
        }

        if (fileAction === "delete") {
            const confirmed = window.confirm(`确认删除文件“${fileName}”吗？`);
            if (!confirmed) {
                return;
            }

            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = "删除中...";
            try {
                await deleteFile(fileId);
                await loadDashboard();
            } catch (error) {
                alert(error.message || "删除失败");
                button.disabled = false;
                button.textContent = originalText;
            }
            return;
        }

        if (fileAction !== "download") {
            return;
        }

        const originalText = button.textContent;
        button.disabled = true;
        button.textContent = "下载中";
        try {
            await downloadPlainFile(fileId, fileName);
        } catch (error) {
            if (error.name !== "AbortError") {
                alert(error.message || "下载失败");
            }
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    });
}

function bindUpdateModal() {
    const modal = document.getElementById("updateFileModal");
    const openButton = document.getElementById("openUpdateFileModal");
    const closeButton = document.getElementById("closeUpdateFileModal");
    const cancelButton = document.getElementById("cancelUpdateFile");
    const nextButton = document.getElementById("nextUpdateFile");
    const backButton = document.getElementById("backUpdateFile");
    const updateFileList = document.getElementById("updateFileList");
    const updateUploadStep = document.getElementById("updateUploadStep");
    const updateFileInput = document.getElementById("updateFileInput");
    const updateFileInputName = document.getElementById("updateFileInputName");

    openButton?.addEventListener("click", openUpdateModal);
    closeButton?.addEventListener("click", closeUpdateModal);
    cancelButton?.addEventListener("click", closeUpdateModal);
    nextButton?.addEventListener("click", goToUpdateUploadStep);
    backButton?.addEventListener("click", () => showUpdateStep("select"));
    updateUploadStep?.addEventListener("submit", submitUpdateFile);

    modal?.addEventListener("click", (event) => {
        if (event.target === modal) {
            closeUpdateModal();
        }
    });

    updateFileList?.addEventListener("change", (event) => {
        const input = event.target.closest("input[name='updateFileChoice']");
        if (input) {
            dashboardState.selectedUpdateFileId = input.value;
            const selectMessage = document.getElementById("updateSelectMessage");
            if (selectMessage) {
                selectMessage.textContent = "";
            }
        }
    });

    updateFileInput?.addEventListener("change", () => {
        const selectedFile = updateFileInput.files?.[0];
        if (updateFileInputName) {
            updateFileInputName.textContent = selectedFile
                ? `${selectedFile.name} · ${formatSize(selectedFile.size)}`
                : "上传后将保留原文件 ID 和编号";
        }
    });
}

async function loadDashboard() {
    const currentUserId = readUserId();
    if (!currentUserId) {
        throw new Error("请先登录");
    }

    const dashboard = await apiJson(`/home/dashboard?user_id=${encodeURIComponent(currentUserId)}`);
    renderSummary(dashboard);
    renderFiles(dashboard.files || []);
}

async function boot() {
    getAuditApp().setupShell?.("dashboard");
    bindFileActions();
    bindUpdateModal();

    try {
        await loadDashboard();
    } catch (error) {
        const message = error.message === "Failed to fetch"
            ? "无法连接后端服务，请先启动 FastAPI"
            : error.message;
        document.getElementById("fileTableBody").innerHTML = `<tr class="empty-row"><td colspan="7">${escapeHtml(message)}</td></tr>`;
    }
}

document.addEventListener("DOMContentLoaded", boot);
