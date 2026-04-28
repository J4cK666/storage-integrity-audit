const API_BASE_URL = "http://127.0.0.1:8000";

function showMessage(message, isError = true) {
    const showMsg = document.getElementById("showMsg");
    showMsg.textContent = message;
    showMsg.style.color = isError ? "#d63d3d" : "#1f9d66";
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

async function register(username, password) {
    const response = await fetch(`${API_BASE_URL}/user/register`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ username, password })
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(formatApiError(data, "注册失败，请稍后再试"));
    }

    return data.user;
}

document.addEventListener("DOMContentLoaded", function() {
    const registerForm = document.getElementById("registerForm");
    const registerButton = registerForm.querySelector(".register-btn");
    const loginLink = document.getElementById("login-link");

    if (loginLink) {
        loginLink.addEventListener("click", function(event) {
            event.preventDefault();
            window.location.href = "../login/login.html";
        });
    }

    registerForm.addEventListener("submit", async function(event) {
        event.preventDefault();

        const username = document.getElementById("username").value.trim();
        const password = document.getElementById("password").value;
        const confirmPassword = document.getElementById("confirmPassword").value;

        if (!username || !password || !confirmPassword) {
            showMessage("请完整填写注册信息");
            return;
        }

        if (password !== confirmPassword) {
            showMessage("两次输入的密码不一致");
            return;
        }

        registerButton.disabled = true;
        registerButton.textContent = "注册中...";
        showMessage("");

        try {
            const user = await register(username, password);
            localStorage.removeItem("auditUser");
            registerForm.reset();
            showMessage(`注册成功，账号ID：${user.account_id}，请前往登录`, false);
            alert(`注册成功！账号ID：${user.account_id}\n请前往登录页面登录。`);
            window.location.href = "../login/login.html";
        } catch (error) {
            showMessage(error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message);
        } finally {
            registerButton.disabled = false;
            registerButton.textContent = "立即注册";
        }
    });
});
