const {
    apiJson,
    escapeHtml,
    makeKeywordPills,
    setupShell,
    statusClass,
    userId
} = window.AuditApp;

let files = [];

const auditKeyword = document.getElementById("auditKeyword");
const runAuditButton = document.getElementById("runAuditButton");

async function loadFiles() {
    const dashboard = await apiJson(`/home/dashboard?user_id=${encodeURIComponent(userId())}`);
    files = dashboard.files || [];
}

function getFileKeywords(fileId) {
    return files.find((file) => file.file_id === fileId)?.keywords || [];
}

function renderAuditSummary(result) {
    document.getElementById("auditResult").innerHTML = `
        <div><span>文件数</span><strong>${result.file_count}</strong></div>
        <div><span>审计结果</span><strong>${escapeHtml(result.audit_result)}</strong></div>
        <div><span>审计时间</span><strong>${escapeHtml(result.audit_time)}</strong></div>
    `;
}

function renderAuditRows(rows, keyword, time) {
    const auditResultBody = document.getElementById("auditResultBody");

    if (!rows.length) {
        auditResultBody.innerHTML = `<tr class="empty-row"><td colspan="4">未命中关键词：${escapeHtml(keyword)}</td></tr>`;
        return;
    }

    auditResultBody.innerHTML = rows.map((file) => `
        <tr>
            <td><strong>${escapeHtml(file.file_name)}</strong><br><span>${escapeHtml(file.file_id)}</span></td>
            <td>${makeKeywordPills(getFileKeywords(file.file_id))}</td>
            <td><span class="status-pill ${statusClass(file.audit_result)}">${escapeHtml(file.audit_result)}</span></td>
            <td>${escapeHtml(time)}</td>
        </tr>
    `).join("");
}

async function runAudit() {
    const keyword = auditKeyword.value.trim();
    if (!keyword) {
        return;
    }

    runAuditButton.disabled = true;
    runAuditButton.textContent = "审计中...";

    try {
        const result = await apiJson("/home/audit", {
            method: "POST",
            body: JSON.stringify({ keyword, user_id: userId() })
        });
        await loadFiles();
        renderAuditSummary(result);
        renderAuditRows(result.files || [], keyword, result.audit_time);
    } catch (error) {
        renderAuditSummary({
            file_count: 0,
            audit_result: error.message === "Failed to fetch" ? "无法连接后端服务" : error.message,
            audit_time: "--"
        });
        renderAuditRows([], keyword, "--");
    } finally {
        runAuditButton.disabled = false;
        runAuditButton.textContent = "开始审计";
    }
}

async function boot() {
    if (!setupShell("audit")) {
        return;
    }

    runAuditButton.addEventListener("click", runAudit);
    auditKeyword.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            runAudit();
        }
    });

    await loadFiles().catch(() => {
        files = [];
    });
}

boot();
