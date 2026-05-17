const {
    apiJson,
    escapeHtml,
    setupShell,
    statusClass,
    statusText,
    userId
} = window.AuditApp;

function recordStatusText(status) {
    const statusMap = {
        complete: "完整",
        broken: "损坏",
        missing: "文件丢失",
        pending: "未审计",
        no_keyword_match: "未命中索引"
    };

    return statusMap[status] || statusText(status);
}

function renderIncludedFiles(files = []) {
    if (!files.length) {
        return `<span class="muted-text">无命中文件</span>`;
    }

    return `
        <div class="record-file-list">
            ${files.map((file) => `
                <div class="record-file-item">
                    <div>
                        <strong>${escapeHtml(file.file_name)}</strong>
                        <span>${escapeHtml(file.file_id)}</span>
                    </div>
                    <span class="status-pill ${statusClass(file.audit_status)}">${escapeHtml(recordStatusText(file.audit_status))}</span>
                </div>
            `).join("")}
        </div>
    `;
}

function renderRecords(records) {
    const recordTableBody = document.getElementById("recordTableBody");

    if (!records.length) {
        recordTableBody.innerHTML = `<tr class="empty-row"><td colspan="5">暂无审计记录</td></tr>`;
        return;
    }

    recordTableBody.innerHTML = records.map((record) => `
        <tr>
            <td><span class="keyword-pill">${escapeHtml(record.keyword)}</span></td>
            <td>${escapeHtml(record.challenge_block_count)}</td>
            <td>${renderIncludedFiles(record.included_files || [])}</td>
            <td><span class="status-pill ${statusClass(record.audit_result)}">${escapeHtml(recordStatusText(record.audit_result))}</span></td>
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
        const message = error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message;
        document.getElementById("recordTableBody").innerHTML = `<tr class="empty-row"><td colspan="5">${escapeHtml(message)}</td></tr>`;
    }
}

boot();
