const ADMIN_IDENTITY_KEY = "auditAdminIdentity";

function setMessage(message) {
    const node = document.getElementById("adminLoginMessage");
    if (node) {
        node.textContent = message;
    }
}

async function loginAdmin(event) {
    event.preventDefault();

    const username = document.getElementById("adminUsername")?.value.trim() || "";
    const password = document.getElementById("adminPassword")?.value || "";
    const button = document.getElementById("adminLoginButton");

    if (!username || !password) {
        setMessage("请输入用户名和密码");
        return;
    }

    button.disabled = true;
    button.textContent = "登录中...";
    setMessage("");

    try {
        const apiBaseUrl = window.AUDIT_CONFIG.API_BASE_URL;
        const response = await fetch(`${apiBaseUrl}/admin/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ username, password })
        });
        const data = await response.json().catch(() => null);

        if (!response.ok) {
            throw new Error(typeof data?.detail === "string" ? data.detail : "登录失败");
        }

        if (data !== "admin") {
            throw new Error("管理员身份校验失败");
        }

        localStorage.setItem(ADMIN_IDENTITY_KEY, data);
        window.location.replace("./admin.html");
    } catch (error) {
        const message = error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message;
        setMessage(message);
    } finally {
        button.disabled = false;
        button.textContent = "登录";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    if (localStorage.getItem(ADMIN_IDENTITY_KEY) === "admin") {
        window.location.replace("./admin.html");
        return;
    }

    document.getElementById("adminLoginForm")?.addEventListener("submit", loginAdmin);
});
