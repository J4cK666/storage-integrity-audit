const API_BASE_URL = "http://127.0.0.1:8000";

function showMessage(message, isError = true) {
    const showMsg = document.getElementById("showMsg");
    showMsg.textContent = message;
    showMsg.style.color = isError ? "#d63d3d" : "#1f9d66";
}

function saveCurrentUser(user) {
    localStorage.setItem("auditUser", JSON.stringify(user));
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

async function login(username, password) {
    const response = await fetch(`${API_BASE_URL}/user/login`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ username, password })
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(formatApiError(data, "登录失败，请检查用户名和密码"));
    }

    return data.user;
}

document.addEventListener("DOMContentLoaded", function() {
    const loginForm = document.getElementById("loginForm");
    const loginButton = document.getElementById("btn-login");
    const registerLink = document.getElementById("register-link");

    if (registerLink) {
        registerLink.addEventListener("click", function(event) {
            event.preventDefault();
            window.location.href = "../register/register.html";
        });
    }

    loginForm.addEventListener("submit", async function(event) {
        event.preventDefault();

        const username = document.getElementById("userAccount").value.trim();
        const password = document.getElementById("userPassword").value;

        if (!username || !password) {
            showMessage("请输入用户名和密码");
            return;
        }

        loginButton.disabled = true;
        loginButton.textContent = "登录中...";
        showMessage("");

        try {
            const user = await login(username, password);
            saveCurrentUser(user);
            showMessage("登录成功，正在进入工作台", false);
            window.location.href = "../home/home.html";
        } catch (error) {
            showMessage(error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message);
        } finally {
            loginButton.disabled = false;
            loginButton.textContent = "立即登录";
        }
    });
});
