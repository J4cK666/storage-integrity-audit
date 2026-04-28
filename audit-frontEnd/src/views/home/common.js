const API_BASE_URL = "http://127.0.0.1:8000";
const currentUser = readCurrentUser();
let shellInteractionsBound = false;

function readCurrentUser() {
    try {
        const user = JSON.parse(localStorage.getItem("auditUser") || "null");
        if (user && !user.account_id && user.user_id) {
            user.account_id = user.user_id;
        }
        return user;
    } catch (error) {
        localStorage.removeItem("auditUser");
        return null;
    }
}

function requireLogin() {
    if (!currentUser || !currentUser.account_id) {
        return false;
    }

    return true;
}

function userId() {
    return currentUser?.account_id || "";
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

function applyCurrentUser() {
    const username = currentUser?.username || "未登录";
    const accountId = currentUser?.account_id || "请先登录";

    document.querySelectorAll(".account-copy strong").forEach((node) => {
        node.textContent = username;
    });
    document.querySelectorAll(".account-copy span").forEach((node) => {
        node.textContent = accountId;
    });
    document.querySelectorAll(".avatar").forEach((node) => {
        node.textContent = username.slice(0, 1).toUpperCase();
    });
}

function applyGuestAccountMenu(accountMenu) {
    if (!accountMenu) {
        return;
    }

    accountMenu.innerHTML = '<a href="../login/login.html">去登录</a>';
}

function updateSidebarToggle(sidebarToggle, appShell) {
    if (!sidebarToggle || !appShell) {
        return;
    }

    const isCollapsed = appShell.classList.contains("nav-collapsed");
    sidebarToggle.setAttribute("aria-expanded", String(!isCollapsed));
    sidebarToggle.setAttribute("title", isCollapsed ? "放大导航栏" : "缩小导航栏");
}

function bindShellInteractions() {
    if (shellInteractionsBound) {
        return;
    }

    const appShell = document.querySelector(".app-shell");
    const sidebarToggle = document.getElementById("sidebarToggle");
    const accountButton = document.getElementById("accountButton");
    const accountMenu = document.getElementById("accountMenu");
    const savedNavState = localStorage.getItem("auditNavCollapsed");

    applyCurrentUser();

    if (!requireLogin()) {
        applyGuestAccountMenu(accountMenu);
    }

    if (appShell && savedNavState === "true") {
        appShell.classList.add("nav-collapsed");
    }
    document.documentElement.classList.remove("nav-collapsed-preload");
    updateSidebarToggle(sidebarToggle, appShell);

    sidebarToggle?.addEventListener("click", (event) => {
        event.preventDefault();
        if (!appShell) {
            return;
        }

        if (window.matchMedia("(max-width: 780px)").matches) {
            appShell.classList.toggle("mobile-nav-open");
            return;
        }

        appShell.classList.toggle("nav-collapsed");
        localStorage.setItem("auditNavCollapsed", String(appShell.classList.contains("nav-collapsed")));
        updateSidebarToggle(sidebarToggle, appShell);
    });

    accountButton?.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!accountMenu) {
            return;
        }

        accountMenu.classList.toggle("open");
    });

    document.addEventListener("click", (event) => {
        if (!accountMenu || !accountButton) {
            return;
        }

        if (!accountButton.contains(event.target) && !accountMenu.contains(event.target)) {
            accountMenu.classList.remove("open");
        }
    });

    document.querySelectorAll("[data-logout]").forEach((link) => {
        link.addEventListener("click", () => {
            localStorage.removeItem("auditUser");
        });
    });

    shellInteractionsBound = true;
}

function setupShell(activePage) {
    bindShellInteractions();

    document.querySelectorAll("[data-page]").forEach((item) => {
        item.classList.toggle("active", item.dataset.page === activePage);
    });

    return requireLogin();
}

document.addEventListener("DOMContentLoaded", bindShellInteractions);

window.AuditApp = {
    apiForm,
    apiJson,
    escapeHtml,
    formatSize,
    makeKeywordPills,
    setupShell,
    statusClass,
    userId
};
