const fallbackRecordsApp = (() => {
    const API_BASE_URL = "http://127.0.0.1:8000";

    function readCurrentUser() {
        try {
            const storedUser = JSON.parse(localStorage.getItem("auditUser") || "null");
            const user = storedUser?.user || storedUser;

            if (user) {
                user.account_id = user.account_id || user.user_id || user.id || "";
                user.username = user.username || user.name || "";
                localStorage.setItem("auditUser", JSON.stringify(user));
            }

            return user;
        } catch (error) {
            localStorage.removeItem("auditUser");
            return null;
        }
    }

    function userId() {
        return readCurrentUser()?.account_id || "";
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function formatApiError(data, fallback) {
        if (typeof data.detail === "string") {
            return data.detail;
        }

        if (Array.isArray(data.detail)) {
            return data.detail.map((item) => item.msg).filter(Boolean).join(", ") || fallback;
        }

        return fallback;
    }

    async function apiJson(path, options = {}) {
        const response = await fetch(`${API_BASE_URL}${path}`, {
            ...options,
            headers: {
                "Content-Type": "application/json",
                ...(options.headers || {})
            }
        });
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(formatApiError(data, "请求失败"));
        }

        return data;
    }

    function statusClass(status) {
        if (status === "complete") {
            return "status-complete";
        }

        if (status === "broken" || status === "missing") {
            return "status-broken";
        }

        return "status-pending";
    }

    function statusText(status) {
        const statusMap = {
            pending: "未审计",
            complete: "完整",
            broken: "损坏",
            missing: "文件丢失"
        };

        return statusMap[status] || status || "未知";
    }

    function setupShell(activePage) {
        window.AuditApp?.setupShell?.(activePage);
        return Boolean(userId());
    }

    return {
        apiJson,
        escapeHtml,
        setupShell,
        statusClass,
        statusText,
        userId
    };
})();

const recordsApp = {
    ...fallbackRecordsApp,
    ...(window.AuditApp || {})
};

const {
    apiJson,
    escapeHtml,
    setupShell,
    statusClass,
    statusText,
    userId
} = recordsApp;

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

function renderProofDetails(record) {
    if (!record.proof_left && !record.proof_right) {
        return `<span class="muted-text">--</span>`;
    }

    return `
        <details class="proof-details">
            <summary>查看</summary>
            <div><strong>左边 e(T, g)</strong><span>${escapeHtml(record.proof_left || "--")}</span></div>
            <div><strong>右边</strong><span>${escapeHtml(record.proof_right || "--")}</span></div>
        </details>
    `;
}

function renderRecords(records) {
    const recordTableBody = document.getElementById("recordTableBody");

    if (!records.length) {
        recordTableBody.innerHTML = `<tr class="empty-row"><td colspan="7">暂无审计记录，请先在文件审计页面完成一次审计</td></tr>`;
        return;
    }

    recordTableBody.innerHTML = records.map((record) => `
        <tr>
            <td><span class="keyword-pill">${escapeHtml(record.keyword)}</span></td>
            <td>${escapeHtml(record.challenge_block_count)}</td>
            <td>${renderIncludedFiles(record.included_files || [])}</td>
            <td><span class="status-pill ${statusClass(record.audit_result)}">${escapeHtml(recordStatusText(record.audit_result))}</span></td>
            <td>${escapeHtml(record.audit_duration || "--")}</td>
            <td>${renderProofDetails(record)}</td>
            <td>${escapeHtml(record.audit_time)}</td>
        </tr>
    `).join("");
}

async function boot() {
    const recordTableBody = document.getElementById("recordTableBody");
    if (!setupShell("records")) {
        recordTableBody.innerHTML = `<tr class="empty-row"><td colspan="7">请先登录后查看审计记录</td></tr>`;
        return;
    }

    try {
        const records = await apiJson(`/home/audit-records?user_id=${encodeURIComponent(userId())}`);
        renderRecords(records || []);
    } catch (error) {
        const message = error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message;
        recordTableBody.innerHTML = `<tr class="empty-row"><td colspan="7">${escapeHtml(message)}</td></tr>`;
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
} else {
    boot();
}
