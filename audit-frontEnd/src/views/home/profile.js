const {
    apiJson,
    setupShell,
    userId
} = window.AuditApp;

const requestKeys = document.getElementById("requestKeys");
const passwordForm = document.getElementById("passwordForm");

function setMessage(id, message, isError = false) {
    const node = document.getElementById(id);
    node.textContent = message;
    node.style.color = isError ? "#d64a4a" : "#1f9d66";
}

async function loadProfile() {
    const profile = await apiJson(`/home/profile?user_id=${encodeURIComponent(userId())}`);
    document.getElementById("profileUsername").textContent = profile.username;
    document.getElementById("profileAccountId").textContent = profile.account_id;
    document.getElementById("profileRole").textContent = profile.role;
    document.getElementById("profilePermissions").textContent = profile.permissions.join("、");
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

async function boot() {
    if (!setupShell("profile")) {
        return;
    }

    requestKeys.addEventListener("click", requestUserKeys);
    passwordForm.addEventListener("submit", changePassword);

    document.querySelectorAll("[data-toggle-secret]").forEach((button) => {
        button.addEventListener("click", () => {
            const input = document.getElementById(button.dataset.toggleSecret);
            input.type = input.type === "password" ? "text" : "password";
        });
    });

    await loadProfile().catch((error) => {
        setMessage("passwordMessage", error.message === "Failed to fetch" ? "无法连接后端服务，请先启动 FastAPI" : error.message, true);
    });
}

boot();
