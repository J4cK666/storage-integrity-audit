const API_BASE_URL = "http://127.0.0.1:8000";
const currentUser = JSON.parse(localStorage.getItem("auditUser") || "null");

const state = {
    files: [],
    pendingFiles: [],
    records: [],
    profile: null
};

const titleMap = {
    dashboard: "首页",
    upload: "上传文件",
    audit: "文件审计",
    records: "审计记录",
    profile: "用户信息"
};

const views = {
    dashboard: document.getElementById("dashboardView"),
    upload: document.getElementById("uploadView"),
    audit: document.getElementById("auditView"),
    records: document.getElementById("recordsView"),
    profile: document.getElementById("profileView")
};

const appShell = document.querySelector(".app-shell");
const navItems = document.querySelectorAll("[data-view]");
const pageTitle = document.getElementById("pageTitle");
const accountButton = document.getElementById("accountButton");
const accountMenu = document.getElementById("accountMenu");
const sidebarToggle = document.getElementById("sidebarToggle");
const fileInput = document.getElementById("fileInput");
const pendingList = document.getElementById("pendingList");
const saveUploads = document.getElementById("saveUploads");
const auditForm = document.getElementById("auditForm");
const auditKeyword = document.getElementById("auditKeyword");
const requestKeys = document.getElementById("requestKeys");
const passwordForm = document.getElementById("passwordForm");

function requireLogin() {
    if (!currentUser || !currentUser.account_id) {
        window.location.href = "../login/login.html";
        return false;
    }

    return true;
}

function userId() {
    return currentUser.account_id;
}

function formatApiError(data, fallback) {
    if (typeof data.detail === "string") {
        return data.detail;
    }

    if (Array.isArray(data.detail)) {
        return data.detail.map((item) => item.msg).filter(Boolean).join("；") || fallback;
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

async function apiForm(path, formData) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
        method: "POST",
        body: formData
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(formatApiError(data, "请求失败"));
    }

    return data;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatSize(size) {
    if (size < 1024) {
        return `${size} B`;
    }

    if (size < 1024 * 1024) {
        return `${(size / 1024).toFixed(1)} KB`;
    }

    return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function makeKeywordPills(keywords = []) {
    return keywords.map((keyword) => `<span class="keyword-pill">${escapeHtml(keyword)}</span>`).join("");
}

function statusClass(status) {
    if (status === "完整") {
        return "status-complete";
    }

    if (status === "损坏") {
        return "status-broken";
    }

    return "status-pending";
}

function getFileKeywords(fileId) {
    return state.files.find((file) => file.file_id === fileId)?.keywords || [];
}

function applyCurrentUser() {
    document.querySelectorAll(".account-copy strong").forEach((node) => {
        node.textContent = currentUser.username;
    });
    document.querySelectorAll(".account-copy span").forEach((node) => {
        node.textContent = currentUser.account_id;
    });
    document.querySelectorAll(".avatar").forEach((node) => {
        node.textContent = currentUser.username.slice(0, 1).toUpperCase();
    });
}

function renderDashboardSummary(dashboard) {
    document.getElementById("fileCount").textContent = dashboard.user_file_count;
    document.getElementById("integrityRatio").textContent = `${dashboard.integrity_ratio}%`;
    document.getElementById("keywordCount").textContent = dashboard.keyword_count;
    document.getElementById("latestAudit").textContent = dashboard.latest_audit_time || "暂无记录";
}

function renderFileTable() {
    const fileTableBody = document.getElementById("fileTableBody");

    if (!state.files.length) {
        fileTableBody.innerHTML = `<tr class="empty-row"><td colspan="5">暂无文件</td></tr>`;
        return;
    }

    fileTableBody.innerHTML = state.files.map((file) => `
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
    state.files = dashboard.files || [];
    renderDashboardSummary(dashboard);
    renderFileTable();
}

function renderPendingFiles() {
    if (!state.pendingFiles.length) {
        pendingList.innerHTML = "";
        return;
    }

    pendingList.innerHTML = state.pendingFiles.map((item, index) => `
        <div class="pending-item">
            <div class="pending-name">
                <strong>${escapeHtml(item.file.name)}</strong>
                <span>${formatSize(item.file.size)}</span>
            </div>
            <input type="text" data-pending-index="${index}" placeholder="输入关键词，多个关键词用逗号分隔" value="${escapeHtml(item.keywords)}">
        </div>
    `).join("");
}

function collectPendingKeywords() {
    document.querySelectorAll("[data-pending-index]").forEach((input) => {
        state.pendingFiles[Number(input.dataset.pendingIndex)].keywords = input.value;
    });
}

async function savePendingFiles() {
    collectPendingKeywords();

    const validItems = state.pendingFiles.filter((item) => item.keywords.trim());
    if (!validItems.length) {
        pendingList.innerHTML = `<div class="empty-row">请为至少一个文件填写关键词</div>`;
        return;
    }

    const formData = new FormData();
    formData.append("user_id", userId());
    validItems.forEach((item) => {
        formData.append("files", item.file);
        formData.append("keywords", item.keywords);
    });

    saveUploads.disabled = true;
    saveUploads.textContent = "上传中...";

    try {
        await apiForm("/home/files/upload", formData);
        state.pendingFiles = [];
        fileInput.value = "";
        renderPendingFiles();
        await loadDashboard();
        switchView("dashboard");
    } catch (error) {
        pendingList.innerHTML = `<div class="empty-row">${escapeHtml(error.message)}</div>`;
    } finally {
        saveUploads.disabled = false;
        saveUploads.textContent = "保存到文件列表";
    }
}

function renderAuditRows(files, keyword, time) {
    const auditResultBody = document.getElementById("auditResultBody");

    if (!files.length) {
        auditResultBody.innerHTML = `<tr class="empty-row"><td colspan="4">未命中关键词：${escapeHtml(keyword)}</td></tr>`;
        return;
    }

    auditResultBody.innerHTML = files.map((file) => `
        <tr>
            <td><strong>${escapeHtml(file.file_name)}</strong><br><span>${escapeHtml(file.file_id)}</span></td>
            <td>${makeKeywordPills(getFileKeywords(file.file_id))}</td>
            <td><span class="status-pill ${statusClass(file.audit_result)}">${escapeHtml(file.audit_result)}</span></td>
            <td>${escapeHtml(time)}</td>
        </tr>
    `).join("");
}

function renderAuditSummary(result) {
    document.getElementById("auditResult").innerHTML = `
        <div>
            <span>文件数</span>
            <strong>${result.file_count}</strong>
        </div>
        <div>
            <span>审计结果</span>
            <strong>${escapeHtml(result.audit_result)}</strong>
        </div>
        <div>
            <span>审计时间</span>
            <strong>${escapeHtml(result.audit_time)}</strong>
        </div>
    `;
}

async function runAudit(event) {
    event.preventDefault();

    const keyword = auditKeyword.value.trim();
    if (!keyword) {
        return;
    }

    const submitButton = auditForm.querySelector("button");
    submitButton.disabled = true;
    submitButton.textContent = "审计中...";

    try {
        const result = await apiJson("/home/audit", {
            method: "POST",
            body: JSON.stringify({ keyword, user_id: userId() })
        });
        renderAuditSummary(result);
        renderAuditRows(result.files || [], keyword, result.audit_time);
        await loadDashboard();
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "开始审计";
    }
}

async function loadRecords() {
    state.records = await apiJson(`/home/audit-records?user_id=${encodeURIComponent(userId())}`);
    renderRecords();
}

function renderRecords() {
    const recordTableBody = document.getElementById("recordTableBody");

    if (!state.records.length) {
        recordTableBody.innerHTML = `<tr class="empty-row"><td colspan="4">暂无审计记录</td></tr>`;
        return;
    }

    recordTableBody.innerHTML = state.records.map((record) => `
        <tr>
            <td><strong>${escapeHtml(record.file_name)}</strong><br><span>${escapeHtml(record.file_id)}</span></td>
            <td><span class="keyword-pill">${escapeHtml(record.keyword)}</span></td>
            <td><span class="status-pill ${statusClass(record.audit_result)}">${escapeHtml(record.audit_result)}</span></td>
            <td>${escapeHtml(record.audit_time)}</td>
        </tr>
    `).join("");
}

async function loadProfile() {
    state.profile = await apiJson(`/home/profile?user_id=${encodeURIComponent(userId())}`);
    document.getElementById("profileUsername").textContent = state.profile.username;
    document.getElementById("profileAccountId").textContent = state.profile.account_id;
    document.getElementById("profileRole").textContent = state.profile.role;
    document.getElementById("profilePermissions").textContent = state.profile.permissions.join("、");
}

function setMessage(id, message, isError = false) {
    const node = document.getElementById(id);
    node.textContent = message;
    node.style.color = isError ? "#d64a4a" : "#1f9d66";
}

async function requestUserKeys() {
    requestKeys.disabled = true;
    requestKeys.textContent = "申请中...";
    setMessage("keyMessage", "");

    try {
        const keys = await apiJson(`/home/profile/keys?user_id=${encodeURIComponent(userId())}`);
        document.getElementById("publicKeyField").value = keys.public_key;
        document.getElementById("privateKeyField").value = keys.private_key;
        document.getElementById("publicKeyField").type = "password";
        document.getElementById("privateKeyField").type = "password";
        setMessage("keyMessage", "密钥已获取，默认以黑点隐藏");
    } catch (error) {
        setMessage("keyMessage", error.message, true);
    } finally {
        requestKeys.disabled = false;
        requestKeys.textContent = "重新申请";
    }
}

async function changePassword(event) {
    event.preventDefault();

    const oldPassword = document.getElementById("oldPassword").value;
    const newPassword = document.getElementById("newPassword").value;
    const confirmNewPassword = document.getElementById("confirmNewPassword").value;

    if (!oldPassword || !newPassword || !confirmNewPassword) {
        setMessage("passwordMessage", "请完整填写密码信息", true);
        return;
    }

    if (newPassword !== confirmNewPassword) {
        setMessage("passwordMessage", "两次输入的新密码不一致", true);
        return;
    }

    const button = passwordForm.querySelector("button");
    button.disabled = true;
    button.textContent = "保存中...";

    try {
        const result = await apiJson("/home/profile/password", {
            method: "POST",
            body: JSON.stringify({
                user_id: userId(),
                old_password: oldPassword,
                new_password: newPassword
            })
        });
        passwordForm.reset();
        setMessage("passwordMessage", result.message);
    } catch (error) {
        setMessage("passwordMessage", error.message, true);
    } finally {
        button.disabled = false;
        button.textContent = "保存新密码";
    }
}

function switchView(viewName) {
    Object.entries(views).forEach(([key, view]) => {
        view.classList.toggle("active", key === viewName);
    });

    document.querySelectorAll(".side-nav .nav-item").forEach((item) => {
        item.classList.toggle("active", item.dataset.view === viewName);
    });

    pageTitle.textContent = titleMap[viewName] || "首页";
    accountMenu.classList.remove("open");
    appShell.classList.remove("mobile-nav-open");

    if (viewName === "records") {
        loadRecords();
    }

    if (viewName === "profile") {
        loadProfile();
    }
}

navItems.forEach((item) => {
    item.addEventListener("click", () => {
        if (item.dataset.view) {
            switchView(item.dataset.view);
        }
    });
});

sidebarToggle.addEventListener("click", () => {
    if (window.matchMedia("(max-width: 780px)").matches) {
        appShell.classList.toggle("mobile-nav-open");
        return;
    }

    appShell.classList.toggle("nav-collapsed");
});

accountButton.addEventListener("click", () => {
    accountMenu.classList.toggle("open");
});

document.querySelectorAll('a[href="../login/login.html"]').forEach((link) => {
    link.addEventListener("click", () => {
        localStorage.removeItem("auditUser");
    });
});

fileInput.addEventListener("change", () => {
    state.pendingFiles = Array.from(fileInput.files).map((file) => ({
        file,
        keywords: ""
    }));
    renderPendingFiles();
});

pendingList.addEventListener("input", collectPendingKeywords);
saveUploads.addEventListener("click", savePendingFiles);
auditForm.addEventListener("submit", runAudit);
requestKeys.addEventListener("click", requestUserKeys);
passwordForm.addEventListener("submit", changePassword);

document.querySelectorAll("[data-toggle-secret]").forEach((button) => {
    button.addEventListener("click", () => {
        const input = document.getElementById(button.dataset.toggleSecret);
        input.type = input.type === "password" ? "text" : "password";
    });
});

async function boot() {
    if (!requireLogin()) {
        return;
    }

    applyCurrentUser();

    try {
        await Promise.all([loadDashboard(), loadProfile(), loadRecords()]);
    } catch (error) {
        document.getElementById("fileTableBody").innerHTML = `<tr class="empty-row"><td colspan="5">${escapeHtml(error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message)}</td></tr>`;
    }
}

boot();
