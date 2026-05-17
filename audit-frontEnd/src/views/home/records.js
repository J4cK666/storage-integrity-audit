const recordsRuntime = (() => {
    const API_BASE_URL = window.AUDIT_CONFIG.API_BASE_URL;

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

    async function apiJson(path) {
        const response = await fetch(`${API_BASE_URL}${path}`, {
            headers: {
                "Content-Type": "application/json"
            }
        });
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(typeof data.detail === "string" ? data.detail : "请求失败");
        }

        return data;
    }

    function statusText(status) {
        const statusMap = {
            pending: "未审计",
            complete: "完整",
            broken: "损坏",
            missing: "文件丢失",
            no_keyword_match: "未命中索引"
        };

        return statusMap[status] || status || "未知";
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
                        <span class="status-pill ${statusClass(file.audit_status)}">${escapeHtml(statusText(file.audit_status))}</span>
                    </div>
                `).join("")}
            </div>
        `;
    }

    function renderRecords(records) {
        const recordTableBody = document.getElementById("recordTableBody");
        if (!recordTableBody) {
            return;
        }

        if (!records.length) {
            recordTableBody.innerHTML = `<tr class="empty-row"><td colspan="6">暂无审计记录，请先在文件审计页面完成一次审计</td></tr>`;
            return;
        }

        recordTableBody.innerHTML = records.map((record) => `
            <tr>
                <td><span class="keyword-pill">${escapeHtml(record.keyword)}</span></td>
                <td>${escapeHtml(record.challenge_block_count)}</td>
                <td>${renderIncludedFiles(record.included_files || [])}</td>
                <td><span class="status-pill ${statusClass(record.audit_result)}">${escapeHtml(statusText(record.audit_result))}</span></td>
                <td>${escapeHtml(record.audit_duration || "--")}</td>
                <td>${escapeHtml(record.audit_time || "--")}</td>
            </tr>
        `).join("");
    }

    async function boot() {
        window.AuditApp?.setupShell?.("records");

        const recordTableBody = document.getElementById("recordTableBody");
        const currentUserId = userId();
        if (!currentUserId) {
            recordTableBody.innerHTML = `<tr class="empty-row"><td colspan="6">请先登录后查看审计记录</td></tr>`;
            return;
        }

        try {
            const records = await apiJson(`/home/audit-records?user_id=${encodeURIComponent(currentUserId)}`);
            renderRecords(records || []);
        } catch (error) {
            const message = error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message;
            recordTableBody.innerHTML = `<tr class="empty-row"><td colspan="6">${escapeHtml(message)}</td></tr>`;
        }
    }

    return {
        boot,
        renderRecords
    };
})();

window.__recordsExternalScriptLoaded = true;

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", recordsRuntime.boot);
} else {
    recordsRuntime.boot();
}
