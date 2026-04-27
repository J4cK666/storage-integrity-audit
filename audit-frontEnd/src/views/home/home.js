const state = {
    files: [
        {
            id: "FID-001",
            name: "f1.txt",
            size: 1832,
            uploadedAt: "2026-04-27 10:08",
            keywords: ["first", "file"],
            status: "未审计"
        },
        {
            id: "FID-002",
            name: "f2.txt",
            size: 2364,
            uploadedAt: "2026-04-27 10:12",
            keywords: ["second", "file"],
            status: "未审计"
        },
        {
            id: "FID-003",
            name: "f3.txt",
            size: 1980,
            uploadedAt: "2026-04-27 10:16",
            keywords: ["third", "world"],
            status: "未审计"
        }
    ],
    pendingFiles: [],
    records: []
};

const currentUser = JSON.parse(localStorage.getItem("auditUser") || "null");

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

function applyCurrentUser() {
    if (!currentUser) {
        return;
    }

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
        renderRecords();
    }
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

function nowText() {
    const value = new Date();
    const pad = (number) => String(number).padStart(2, "0");
    return [
        value.getFullYear(),
        pad(value.getMonth() + 1),
        pad(value.getDate())
    ].join("-") + " " + [
        pad(value.getHours()),
        pad(value.getMinutes())
    ].join(":");
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function makeKeywordPills(keywords) {
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

function renderDashboard() {
    const fileTableBody = document.getElementById("fileTableBody");
    const keywords = new Set(state.files.flatMap((file) => file.keywords));
    const completeFiles = state.files.filter((file) => file.status !== "损坏").length;
    const ratio = state.files.length ? Math.round((completeFiles / state.files.length) * 100) : 100;

    document.getElementById("fileCount").textContent = state.files.length;
    document.getElementById("integrityRatio").textContent = `${ratio}%`;
    document.getElementById("keywordCount").textContent = keywords.size;
    document.getElementById("latestAudit").textContent = state.records[0]?.time || "暂无记录";

    if (!state.files.length) {
        fileTableBody.innerHTML = `<tr class="empty-row"><td colspan="5">暂无文件</td></tr>`;
        return;
    }

    fileTableBody.innerHTML = state.files.map((file) => `
        <tr>
            <td><strong>${escapeHtml(file.name)}</strong><br><span>${escapeHtml(file.id)}</span></td>
            <td>${formatSize(file.size)}</td>
            <td>${file.uploadedAt}</td>
            <td>${makeKeywordPills(file.keywords)}</td>
            <td><span class="status-pill ${statusClass(file.status)}">${file.status}</span></td>
        </tr>
    `).join("");
}

function renderPendingFiles() {
    if (!state.pendingFiles.length) {
        pendingList.innerHTML = "";
        return;
    }

    pendingList.innerHTML = state.pendingFiles.map((file, index) => `
        <div class="pending-item">
            <div class="pending-name">
                <strong>${escapeHtml(file.name)}</strong>
                <span>${formatSize(file.size)}</span>
            </div>
            <input type="text" data-pending-index="${index}" placeholder="输入关键词，多个关键词用逗号分隔" value="${escapeHtml(file.keywords)}">
        </div>
    `).join("");
}

function collectPendingKeywords() {
    document.querySelectorAll("[data-pending-index]").forEach((input) => {
        const index = Number(input.dataset.pendingIndex);
        state.pendingFiles[index].keywords = input.value;
    });
}

function savePendingFiles() {
    collectPendingKeywords();

    const nextFiles = state.pendingFiles.map((file, index) => ({
        id: `FID-${String(state.files.length + index + 1).padStart(3, "0")}`,
        name: file.name,
        size: file.size,
        uploadedAt: nowText(),
        keywords: file.keywords.split(/[,，\s]+/).map((item) => item.trim()).filter(Boolean),
        status: "未审计"
    })).filter((file) => file.keywords.length);

    if (!nextFiles.length) {
        return;
    }

    state.files = [...nextFiles, ...state.files];
    state.pendingFiles = [];
    fileInput.value = "";
    renderPendingFiles();
    renderDashboard();
    switchView("dashboard");
}

function renderAuditRows(rows, keyword, time) {
    const auditResultBody = document.getElementById("auditResultBody");

    if (!rows.length) {
        auditResultBody.innerHTML = `<tr class="empty-row"><td colspan="4">未命中关键词：${escapeHtml(keyword)}</td></tr>`;
        return;
    }

    auditResultBody.innerHTML = rows.map((file) => `
        <tr>
            <td><strong>${escapeHtml(file.name)}</strong><br><span>${escapeHtml(file.id)}</span></td>
            <td>${makeKeywordPills(file.keywords)}</td>
            <td><span class="status-pill status-complete">完整</span></td>
            <td>${time}</td>
        </tr>
    `).join("");
}

function runAudit(event) {
    event.preventDefault();

    const keyword = auditKeyword.value.trim();
    if (!keyword) {
        return;
    }

    const time = nowText();
    const matchedFiles = state.files.filter((file) => {
        return file.keywords.some((item) => item.toLowerCase() === keyword.toLowerCase());
    });

    matchedFiles.forEach((file) => {
        file.status = "完整";
    });

    const resultText = matchedFiles.length ? "ProofVerify 通过" : "未命中索引";
    const auditResult = document.getElementById("auditResult");
    auditResult.innerHTML = `
        <div>
            <span>文件数</span>
            <strong>${matchedFiles.length}</strong>
        </div>
        <div>
            <span>审计结果</span>
            <strong>${resultText}</strong>
        </div>
        <div>
            <span>审计时间</span>
            <strong>${time}</strong>
        </div>
    `;

    matchedFiles.forEach((file) => {
        state.records.unshift({
            id: file.id,
            name: file.name,
            keyword,
            result: "完整",
            time
        });
    });

    renderAuditRows(matchedFiles, keyword, time);
    renderDashboard();
}

function renderRecords() {
    const recordTableBody = document.getElementById("recordTableBody");

    if (!state.records.length) {
        recordTableBody.innerHTML = `<tr class="empty-row"><td colspan="4">暂无审计记录</td></tr>`;
        return;
    }

    recordTableBody.innerHTML = state.records.map((record) => `
        <tr>
            <td><strong>${escapeHtml(record.name)}</strong><br><span>${escapeHtml(record.id)}</span></td>
            <td><span class="keyword-pill">${escapeHtml(record.keyword)}</span></td>
            <td><span class="status-pill ${statusClass(record.result)}">${record.result}</span></td>
            <td>${record.time}</td>
        </tr>
    `).join("");
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
        name: file.name,
        size: file.size,
        keywords: ""
    }));
    renderPendingFiles();
});

pendingList.addEventListener("input", collectPendingKeywords);
saveUploads.addEventListener("click", savePendingFiles);
auditForm.addEventListener("submit", runAudit);

applyCurrentUser();
renderDashboard();
renderRecords();
