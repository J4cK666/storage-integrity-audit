const {
    apiJson,
    escapeHtml,
    formatSize,
    makeKeywordPills,
    setupShell,
    statusClass,
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
        fileTableBody.innerHTML = `<tr class="empty-row"><td colspan="5">暂无文件</td></tr>`;
        return;
    }

    fileTableBody.innerHTML = files.map((file) => `
        <tr>
            <td><strong>${escapeHtml(file.file_name)}</strong><br><span>${escapeHtml(file.file_id)}</span></td>
            <td>${formatSize(file.file_size)}</td>
            <td>${escapeHtml(file.upload_time)}</td>
            <td>${makeKeywordPills(file.keywords)}</td>
            <td><span class="status-pill ${statusClass(file.audit_status)}">${escapeHtml(file.audit_status)}</span></td>
        </tr>
    `).join("");
}

async function loadDashboard() {
    const dashboard = await apiJson(`/home/dashboard?user_id=${encodeURIComponent(userId())}`);
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
        document.getElementById("fileTableBody").innerHTML = `<tr class="empty-row"><td colspan="5">${escapeHtml(error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message)}</td></tr>`;
    }
}

boot();
