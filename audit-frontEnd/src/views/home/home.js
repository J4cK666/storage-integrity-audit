const API_BASE_URL_FALLBACK = "http://127.0.0.1:8000";

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

async function apiJson(path) {
    const appApiJson = getAuditApp().apiJson;
    if (appApiJson) {
        return appApiJson(path);
    }

    const response = await fetch(`${API_BASE_URL_FALLBACK}${path}`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "请求失败");
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

    if (!files.length) {
        fileTableBody.innerHTML = `<tr class="empty-row"><td colspan="6">暂无文件</td></tr>`;
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
        </tr>
    `).join("");
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

    try {
        await loadDashboard();
    } catch (error) {
        const message = error.message === "Failed to fetch"
            ? "无法连接后端服务，请先启动 FastAPI"
            : error.message;
        document.getElementById("fileTableBody").innerHTML = `<tr class="empty-row"><td colspan="6">${escapeHtml(message)}</td></tr>`;
    }
}

document.addEventListener("DOMContentLoaded", boot);
