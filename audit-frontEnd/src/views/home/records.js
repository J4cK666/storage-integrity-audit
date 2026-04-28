const {
    apiJson,
    escapeHtml,
    setupShell,
    statusClass,
    userId
} = window.AuditApp;

function renderRecords(records) {
    const recordTableBody = document.getElementById("recordTableBody");

    if (!records.length) {
        recordTableBody.innerHTML = `<tr class="empty-row"><td colspan="4">暂无审计记录</td></tr>`;
        return;
    }

    recordTableBody.innerHTML = records.map((record) => `
        <tr>
            <td><strong>${escapeHtml(record.file_name)}</strong><br><span>${escapeHtml(record.file_id)}</span></td>
            <td><span class="keyword-pill">${escapeHtml(record.keyword)}</span></td>
            <td><span class="status-pill ${statusClass(record.audit_result)}">${escapeHtml(record.audit_result)}</span></td>
            <td>${escapeHtml(record.audit_time)}</td>
        </tr>
    `).join("");
}

async function boot() {
    if (!setupShell("records")) {
        return;
    }

    try {
        const records = await apiJson(`/home/audit-records?user_id=${encodeURIComponent(userId())}`);
        renderRecords(records || []);
    } catch (error) {
        document.getElementById("recordTableBody").innerHTML = `<tr class="empty-row"><td colspan="4">${escapeHtml(error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message)}</td></tr>`;
    }
}

boot();
