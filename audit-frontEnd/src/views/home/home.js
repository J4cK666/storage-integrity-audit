const {
    apiJson,
    escapeHtml,
    formatSize,
    makeKeywordPills,
    setupShell,
    statusClass,
    statusText,
    userId
} = window.AuditApp;

function renderSummary(dashboard) {
    document.getElementById("fileCount").textContent = dashboard.user_file_count;
    document.getElementById("integrityRatio").textContent = `${dashboard.integrity_ratio}%`;
    document.getElementById("keywordCount").textContent = dashboard.keyword_count;
    document.getElementById("latestAudit").textContent = dashboard.latest_audit_time || "暂无记录";
}

function renderFiles(files) {
    const fileTableBody = document.getElementById("fileTableBody");

    if (!files.length) {
        fileTableBody.innerHTML = `<tr class="empty-row"><td colspan="6">暂无文件</td></tr>`;
        return;
    }

    fileTableBody.innerHTML = files.map((file) => `
        <tr>
            <td><strong>${escapeHtml(file.file_name)}</strong><br><span>${escapeHtml(file.file_id)}</span></td>
            <td>${formatSize(file.file_size)}</td>
            <td>${escapeHtml(file.upload_time)}</td>
            <td>${makeKeywordPills(file.keywords)}</td>
            <td><span class="status-pill ${statusClass(file.audit_status)}">${escapeHtml(statusText(file.audit_status))}</span></td>
            <td>${escapeHtml(file.last_audit_time || "暂无记录")}</td>
        </tr>
    `).join("");
}

async function loadDashboard() {
    const currentUserId = userId();
    if (!currentUserId) {
        throw new Error("请先登录");
    }

    const dashboard = await apiJson(`/home/dashboard?user_id=${encodeURIComponent(currentUserId)}`);
    renderSummary(dashboard);
    renderFiles(dashboard.files || []);
}

async function boot() {
    if (!setupShell("dashboard")) {
        return;
    }

    try {
        await loadDashboard();
    } catch (error) {
        const message = error.message === "Failed to fetch"
            ? "无法连接后端服务，请先启动 FastAPI"
            : error.message;
        document.getElementById("fileTableBody").innerHTML = `<tr class="empty-row"><td colspan="6">${escapeHtml(message)}</td></tr>`;
    }
}

boot();
