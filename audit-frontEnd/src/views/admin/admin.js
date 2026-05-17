const adminRuntime = (() => {
    const ADMIN_IDENTITY_KEY = "auditAdminIdentity";
    const tabTitles = {
        users: "用户列表",
        files: "文件列表",
        records: "审计列表"
    };

    function ensureLogin() {
        if (localStorage.getItem(ADMIN_IDENTITY_KEY) === "admin") {
            return true;
        }

        window.location.replace("./alogin.html");
        return false;
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
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

    async function apiJson(path) {
        const apiBaseUrl = window.AUDIT_CONFIG.API_BASE_URL;
        const response = await fetch(`${apiBaseUrl}${path}`, {
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

    function setText(id, value) {
        const node = document.getElementById(id);
        if (node) {
            node.textContent = value;
        }
    }

    function setTableMessage(bodyId, colspan, message) {
        const body = document.getElementById(bodyId);
        if (body) {
            body.innerHTML = `<tr class="empty-row"><td colspan="${colspan}">${escapeHtml(message)}</td></tr>`;
        }
    }

    function switchTab(tabName) {
        document.querySelectorAll("[data-admin-tab]").forEach((button) => {
            button.classList.toggle("active", button.dataset.adminTab === tabName);
        });
        document.querySelectorAll("[data-admin-panel]").forEach((panel) => {
            panel.classList.toggle("active", panel.dataset.adminPanel === tabName);
        });
        setText("adminPageTitle", tabTitles[tabName] || "管理员");
    }

    function renderUsers(users) {
        const body = document.getElementById("adminUserTableBody");
        if (!body) {
            return;
        }

        setText("adminUserCount", users.length);
        if (!users.length) {
            setTableMessage("adminUserTableBody", 2, "暂无用户");
            return;
        }

        body.innerHTML = users.map((user) => `
            <tr>
                <td>
                    <button class="admin-user-button" type="button" data-user-id="${escapeHtml(user.account_id)}">
                        ${escapeHtml(user.username)}
                    </button>
                </td>
                <td><span class="admin-id">${escapeHtml(user.account_id)}</span></td>
            </tr>
        `).join("");
    }

    function renderFiles(files) {
        const body = document.getElementById("adminFileTableBody");
        if (!body) {
            return;
        }

        setText("selectedFileCount", files.length);
        if (!files.length) {
            setTableMessage("adminFileTableBody", 3, "该用户暂无文件记录");
            return;
        }

        body.innerHTML = files.map((file) => `
            <tr>
                <td><span class="admin-id">${escapeHtml(file.file_id)}</span></td>
                <td><span class="status-pill ${statusClass(file.audit_status)}">${escapeHtml(statusText(file.audit_status))}</span></td>
                <td>${escapeHtml(file.last_audit_time || "暂无审计")}</td>
            </tr>
        `).join("");
    }

    function renderRecords(records) {
        const body = document.getElementById("adminRecordTableBody");
        if (!body) {
            return;
        }

        setText("selectedRecordCount", records.length);
        if (!records.length) {
            setTableMessage("adminRecordTableBody", 3, "该用户暂无审计记录");
            return;
        }

        body.innerHTML = records.map((record) => `
            <tr>
                <td><span class="admin-id">${escapeHtml(record.record_id)}</span></td>
                <td><span class="status-pill ${statusClass(record.audit_result)}">${escapeHtml(statusText(record.audit_result))}</span></td>
                <td>${escapeHtml(record.audit_time || "--")}</td>
            </tr>
        `).join("");
    }

    async function loadUsers() {
        setTableMessage("adminUserTableBody", 2, "正在读取用户...");
        try {
            const users = await apiJson("/admin/users");
            renderUsers(Array.isArray(users) ? users : []);
        } catch (error) {
            const message = error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message;
            setTableMessage("adminUserTableBody", 2, message);
            setText("adminUserCount", 0);
        }
    }

    async function loadFilesByUserId(userId) {
        const cleanUserId = userId.trim();
        if (!cleanUserId) {
            setTableMessage("adminFileTableBody", 3, "请输入用户 ID 后查询");
            setText("fileSelectedUserId", "--");
            setText("selectedFileCount", 0);
            return;
        }

        setText("fileSelectedUserId", cleanUserId);
        setTableMessage("adminFileTableBody", 3, "正在读取文件列表...");
        try {
            const files = await apiJson(`/admin/users/${encodeURIComponent(cleanUserId)}/files`);
            renderFiles(Array.isArray(files) ? files : []);
        } catch (error) {
            const message = error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message;
            setTableMessage("adminFileTableBody", 3, message);
            setText("selectedFileCount", 0);
        }
    }

    async function loadRecordsByUserId(userId) {
        const cleanUserId = userId.trim();
        if (!cleanUserId) {
            setTableMessage("adminRecordTableBody", 3, "请输入用户 ID 后查询");
            setText("recordSelectedUserId", "--");
            setText("selectedRecordCount", 0);
            return;
        }

        setText("recordSelectedUserId", cleanUserId);
        setTableMessage("adminRecordTableBody", 3, "正在读取审计记录...");
        try {
            const records = await apiJson(`/admin/users/${encodeURIComponent(cleanUserId)}/audit-records`);
            renderRecords(Array.isArray(records) ? records : []);
        } catch (error) {
            const message = error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message;
            setTableMessage("adminRecordTableBody", 3, message);
            setText("selectedRecordCount", 0);
        }
    }

    function bindNavigation() {
        document.querySelectorAll("[data-admin-tab]").forEach((button) => {
            button.addEventListener("click", () => switchTab(button.dataset.adminTab));
        });
    }

    function bindQueries() {
        document.getElementById("refreshUsersButton")?.addEventListener("click", loadUsers);

        document.getElementById("fileQueryForm")?.addEventListener("submit", (event) => {
            event.preventDefault();
            loadFilesByUserId(document.getElementById("fileUserIdInput")?.value || "");
        });

        document.getElementById("recordQueryForm")?.addEventListener("submit", (event) => {
            event.preventDefault();
            loadRecordsByUserId(document.getElementById("recordUserIdInput")?.value || "");
        });

        document.getElementById("adminUserTableBody")?.addEventListener("click", (event) => {
            const button = event.target.closest("[data-user-id]");
            if (!button) {
                return;
            }

            const userId = button.dataset.userId;
            document.getElementById("fileUserIdInput").value = userId;
            document.getElementById("recordUserIdInput").value = userId;
            switchTab("files");
            loadFilesByUserId(userId);
        });
    }

    function bindLogout() {
        document.getElementById("adminLogout")?.addEventListener("click", () => {
            localStorage.removeItem(ADMIN_IDENTITY_KEY);
            window.location.replace("./alogin.html");
        });
    }

    async function boot() {
        const canEnterAdmin = typeof ensureLogin === "function" ? ensureLogin() : true;
        if (!canEnterAdmin) {
            return;
        }

        bindNavigation();
        bindQueries();
        bindLogout();
        switchTab("users");
        await loadUsers();
    }

    return {
        boot,
        loadFilesByUserId,
        loadRecordsByUserId,
        loadUsers,
        switchTab
    };
})();

document.addEventListener("DOMContentLoaded", adminRuntime.boot);
