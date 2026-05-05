const API_BASE_URL = "http://127.0.0.1:8000";
const REGISTER_SUCCESS_KEY = "auditRegisterSuccess";

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

function openSuccessModal(user) {
    const successModal = document.getElementById("successModal");
    const successMessage = document.getElementById("successMessage");
    const accountId = user?.account_id || "--";

    successMessage.textContent = `注册成功，账号ID：${accountId}。请前往登录页面登录。`;
    successModal.classList.add("open");
    successModal.setAttribute("aria-hidden", "false");
}

function rememberRegisterSuccess(user) {
    sessionStorage.setItem(REGISTER_SUCCESS_KEY, JSON.stringify({
        account_id: user?.account_id || "--"
    }));
}

function restoreRegisterSuccess() {
    const rawSuccess = sessionStorage.getItem(REGISTER_SUCCESS_KEY);
    if (!rawSuccess) {
        return;
    }

    try {
        openSuccessModal(JSON.parse(rawSuccess));
    } catch (error) {
        sessionStorage.removeItem(REGISTER_SUCCESS_KEY);
    }
}

document.addEventListener("DOMContentLoaded", function() {
    const registerForm = document.getElementById("registerForm");
    const registerButton = registerForm.querySelector(".register-btn");
    const loginLink = document.getElementById("login-link");
    const successLoginButton = document.getElementById("successLoginButton");
    let isSubmitting = false;

    successLoginButton.addEventListener("click", function(event) {
        event.preventDefault();
        sessionStorage.removeItem(REGISTER_SUCCESS_KEY);
        window.location.href = "../login/login.html";
    });

    if (loginLink) {
        loginLink.addEventListener("click", function(event) {
            event.preventDefault();
            window.location.href = "../login/login.html";
        });
    }

    async function handleRegister(event) {
        event?.preventDefault();
        event?.stopPropagation();

        if (isSubmitting) {
            return;
        }

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

        isSubmitting = true;
        registerButton.disabled = true;
        registerButton.textContent = "注册中...";
        showMessage("");

        try {
            const user = await register(username, password);
            localStorage.removeItem("auditUser");
            rememberRegisterSuccess(user);
            registerForm.reset();
            showMessage(`注册成功，账号ID：${user.account_id}，请前往登录`, false);
            openSuccessModal(user);
        } catch (error) {
            showMessage(error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message);
        } finally {
            isSubmitting = false;
            registerButton.disabled = false;
            registerButton.textContent = "立即注册";
        }
    }

    registerButton.addEventListener("click", handleRegister);
    registerForm.addEventListener("submit", handleRegister);
    restoreRegisterSuccess();
});
