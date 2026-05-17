const fallbackAuditApp = (() => {
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

    function makeKeywordPills(keywords = []) {
        return keywords.map((keyword) => `<span class="keyword-pill">${escapeHtml(keyword)}</span>`).join("");
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

    function userId() {
        return readCurrentUser()?.account_id || "";
    }

    function setupShell(activePage) {
        window.AuditApp?.setupShell?.(activePage);
        return Boolean(userId());
    }

    return {
        apiJson,
        escapeHtml,
        makeKeywordPills,
        setupShell,
        statusClass,
        userId
    };
})();

const auditApp = {
    ...fallbackAuditApp,
    ...(window.AuditApp || {})
};

const {
    apiJson,
    escapeHtml,
    makeKeywordPills,
    setupShell,
    statusClass,
    userId
} = auditApp;

let files = [];
let maxAuditBlockCount = 0;

const auditKeyword = document.getElementById("auditKeyword");
const auditBlockCount = document.getElementById("auditBlockCount");
const auditBlockHint = document.getElementById("auditBlockHint");
const runAuditButton = document.getElementById("runAuditButton");

const auditResultTextMap = {
    complete: "完整",
    broken: "损坏",
    missing: "文件丢失",
    pending: "未审计",
    no_keyword_match: "未命中索引",
    proof_verify_passed: "ProofVerify 通过",
    secure_index_not_found: "未找到安全索引",
    challenge_block_count_out_of_range: "审计块数超出范围"
};

function withTimeout(promise, message, timeoutMs = 8000) {
    let timeoutId;
    const timeout = new Promise((_, reject) => {
        timeoutId = window.setTimeout(() => reject(new Error(message)), timeoutMs);
    });

    return Promise.race([promise, timeout]).finally(() => {
        window.clearTimeout(timeoutId);
    });
}

function showError(message) {
    auditBlockHint.textContent = message;
    window.alert(message);
}

function auditResultText(value) {
    return auditResultTextMap[value] || value || "未知";
}

async function loadFiles() {
    const dashboard = await apiJson(`/home/dashboard?user_id=${encodeURIComponent(userId())}`);
    files = dashboard.files || [];
}

function getFileKeywords(fileId) {
    return files.find((file) => file.file_id === fileId)?.keywords || [];
}

function setBlockPickerDisabled(message) {
    maxAuditBlockCount = 0;
    auditBlockCount.value = "";
    auditBlockCount.min = "1";
    auditBlockCount.removeAttribute("max");
    auditBlockCount.disabled = true;
    auditBlockHint.textContent = message;
}

function renderBlockPicker(maxBlockCount) {
    maxAuditBlockCount = Number(maxBlockCount) || 0;

    if (maxAuditBlockCount < 1) {
        setBlockPickerDisabled("未读取到安全索引，请先上传文件");
        return;
    }

    auditBlockCount.disabled = false;
    auditBlockCount.min = "1";
    auditBlockCount.max = String(maxAuditBlockCount);
    auditBlockCount.value = "1";
    auditBlockHint.textContent = `可选范围：1 - ${maxAuditBlockCount}`;
}

async function loadAuditOptions() {
    setBlockPickerDisabled("正在读取安全索引...");
    const currentUserId = userId();
    if (!currentUserId) {
        throw new Error("未读取到登录用户，请重新登录");
    }

    const options = await withTimeout(
        apiJson(`/home/audit/options?user_id=${encodeURIComponent(currentUserId)}`),
        "安全索引读取超时，请检查后端服务"
    );

    if (!Number(options.max_block_count)) {
        throw new Error("未读取到安全索引，请先上传文件或检查云端 .index 文件");
    }

    renderBlockPicker(options.max_block_count);
}

function normalizeBlockCount() {
    const selected = Number(auditBlockCount.value);

    if (!Number.isInteger(selected)) {
        return 0;
    }

    return selected;
}

function renderAuditSummary(result) {
    document.getElementById("auditResult").innerHTML = `
        <div><span>文件数</span><strong>${result.file_count}</strong></div>
        <div><span>审计块数</span><strong>${escapeHtml(result.challenge_block_count ?? "--")}</strong></div>
        <div><span>审计结果</span><strong>${escapeHtml(auditResultText(result.audit_result))}</strong></div>
        <div><span>审计用时</span><strong>${escapeHtml(result.audit_duration ?? "--")}</strong></div>
    `;
}

function renderAuditRows(rows, keyword, duration) {
    const auditResultBody = document.getElementById("auditResultBody");

    if (!rows.length) {
        auditResultBody.innerHTML = `<tr class="empty-row"><td colspan="4">未命中关键词：${escapeHtml(keyword)}</td></tr>`;
        return;
    }

    auditResultBody.innerHTML = rows.map((file) => `
        <tr>
            <td><strong>${escapeHtml(file.file_name)}</strong><br><span>${escapeHtml(file.file_id)}</span></td>
            <td>${makeKeywordPills(getFileKeywords(file.file_id))}</td>
            <td><span class="status-pill ${statusClass(file.audit_result)}">${escapeHtml(auditResultText(file.audit_result))}</span></td>
            <td>${escapeHtml(duration)}</td>
        </tr>
    `).join("");
}

async function runAudit() {
    const keyword = auditKeyword.value.trim();
    const challengeBlockCount = normalizeBlockCount();

    if (!keyword) {
        auditKeyword.focus();
        return;
    }

    if (maxAuditBlockCount < 1) {
        showError("未读取到安全索引，不能发起审计");
        return;
    }

    if (challengeBlockCount < 1 || challengeBlockCount > maxAuditBlockCount) {
        auditBlockHint.textContent = `请输入 1 - ${maxAuditBlockCount} 之间的审计块数`;
        auditBlockCount.focus();
        return;
    }

    runAuditButton.disabled = true;
    runAuditButton.textContent = "审计中...";

    try {
        const result = await apiJson("/home/audit", {
            method: "POST",
            body: JSON.stringify({
                keyword,
                user_id: userId(),
                challenge_block_count: challengeBlockCount
            })
        });
        await loadFiles();
        renderAuditSummary(result);
        renderAuditRows(result.files || [], keyword, result.audit_duration || "--");
    } catch (error) {
        const message = error.message === "Failed to fetch" ? "无法连接后端服务" : error.message;
        renderAuditSummary({
            challenge_block_count: challengeBlockCount || "--",
            file_count: 0,
            audit_result: message,
            audit_duration: "--",
            audit_time: "--"
        });
        renderAuditRows([], keyword, "--");
        window.alert(message);
    } finally {
        runAuditButton.disabled = false;
        runAuditButton.textContent = "开始审计";
    }
}

async function boot() {
    try {
        if (!setupShell("audit")) {
            setBlockPickerDisabled("请先登录后审计");
            runAuditButton.disabled = true;
            return;
        }

        runAuditButton.addEventListener("click", runAudit);
        auditKeyword.addEventListener("keydown", (event) => {
            if (event.key === "Enter") {
                event.preventDefault();
                runAudit();
            }
        });
        auditBlockCount.addEventListener("change", () => {
            const selected = normalizeBlockCount();
            if (selected >= 1 && selected <= maxAuditBlockCount) {
                auditBlockHint.textContent = `可选范围：1 - ${maxAuditBlockCount}`;
            }
        });

        await Promise.all([
            loadFiles().catch(() => {
                files = [];
            }),
            loadAuditOptions().catch((error) => {
                showError(error.message || "安全索引读取失败");
            })
        ]);
    } catch (error) {
        showError(error.message || "文件审计页面初始化失败");
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
} else {
    boot();
}
