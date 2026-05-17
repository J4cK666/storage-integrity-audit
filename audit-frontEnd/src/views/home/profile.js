(function() {
    const SECRET_ICON_SHOW = "../../assets/icons/eye-show.svg";
    const SECRET_ICON_HIDE = "../../assets/icons/eye-hide.svg";

    function getStoredUser() {
        try {
            const storedUser = JSON.parse(localStorage.getItem("auditUser") || "null");
            const user = storedUser?.user || storedUser;

            if (!user) {
                return null;
            }

            return {
                ...user,
                account_id: user.account_id || user.user_id || user.id || "",
                username: user.username || user.name || ""
            };
        } catch (error) {
            localStorage.removeItem("auditUser");
            return null;
        }
    }

    function setText(id, value) {
        const node = document.getElementById(id);
        if (node) {
            node.textContent = value;
        }
    }

    function setMessage(id, message, isError = false) {
        const node = document.getElementById(id);
        if (!node) {
            return;
        }

        node.textContent = message;
        node.style.color = isError ? "#d64a4a" : "#1f9d66";
    }

    function renderProfile(profile) {
        setText("profileUsername", profile.username || "未登录");
        setText("profileAccountId", profile.account_id || profile.user_id || "--");
        setText("profileRole", profile.role || "User");
        setText(
            "profilePermissions",
            Array.isArray(profile.permissions)
                ? profile.permissions.join("、")
                : "文件上传、关键词审计、记录查看"
        );
    }

    function renderProfileFromLoginState() {
        const currentUser = getStoredUser();

        if (!currentUser || !currentUser.account_id) {
            renderProfile({
                username: "未登录",
                account_id: "--",
                role: "Guest",
                permissions: ["请先登录"]
            });
            return null;
        }

        renderProfile({
            username: currentUser.username,
            account_id: currentUser.account_id,
            role: "User",
            permissions: ["文件上传", "关键词审计", "审计记录查看"]
        });
        return currentUser;
    }

    function getAuditApp() {
        return window.AuditApp || {};
    }

    function secretName(input) {
        return input.id === "privateKeyField" ? "私钥" : "公钥";
    }

    function updateSecretButton(button, input) {
        const isVisible = input.type === "text";
        const img = button.querySelector("img");
        const action = isVisible ? "隐藏" : "显示";
        const label = `${action}${secretName(input)}`;

        if (img) {
            img.src = isVisible ? SECRET_ICON_HIDE : SECRET_ICON_SHOW;
        }
        button.setAttribute("aria-label", label);
        button.setAttribute("title", label);
        button.classList.toggle("is-visible", isVisible);
    }

    function setSecretVisible(input, visible) {
        input.type = visible ? "text" : "password";
        document
            .querySelectorAll(`[data-toggle-secret="${input.id}"]`)
            .forEach((button) => updateSecretButton(button, input));
    }

    async function loadProfile(user) {
        const { apiJson } = getAuditApp();
        if (!apiJson || !user?.account_id) {
            return;
        }

        const profile = await apiJson(`/home/profile?user_id=${encodeURIComponent(user.account_id)}`);
        renderProfile(profile);
    }

    async function requestUserKeys(event) {
        event.preventDefault();

        const user = getStoredUser();
        const { apiJson } = getAuditApp();
        const requestKeys = document.getElementById("requestKeys");

        if (!apiJson || !user?.account_id) {
            setMessage("keyMessage", "请先登录后查看密钥", true);
            return;
        }

        requestKeys.disabled = true;
        requestKeys.textContent = "申请中...";
        setMessage("keyMessage", "");

        try {
            const keys = await apiJson(`/home/profile/keys?user_id=${encodeURIComponent(user.account_id)}`);
            document.getElementById("publicKeyField").value = keys.public_key;
            document.getElementById("privateKeyField").value = keys.private_key;
            setSecretVisible(document.getElementById("publicKeyField"), false);
            setSecretVisible(document.getElementById("privateKeyField"), false);
            setMessage("keyMessage", "密钥已获取");
        } catch (error) {
            setMessage("keyMessage", error.message, true);
        } finally {
            requestKeys.disabled = false;
            requestKeys.textContent = "重新申请";
        }
    }

    async function changePassword(event) {
        event.preventDefault();

        const user = getStoredUser();
        const { apiJson } = getAuditApp();
        const passwordForm = document.getElementById("passwordForm");
        const oldPassword = document.getElementById("oldPassword").value;
        const newPassword = document.getElementById("newPassword").value;
        const confirmNewPassword = document.getElementById("confirmNewPassword").value;

        if (!apiJson || !user?.account_id) {
            setMessage("passwordMessage", "请先登录后修改密码", true);
            return;
        }

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
                    user_id: user.account_id,
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
        const user = renderProfileFromLoginState();
        const { setupShell } = getAuditApp();

        if (setupShell) {
            setupShell("profile");
        }

        document.getElementById("requestKeys")?.addEventListener("click", requestUserKeys);
        document.getElementById("passwordForm")?.addEventListener("submit", changePassword);

        document.querySelectorAll("[data-toggle-secret]").forEach((button) => {
            const input = document.getElementById(button.dataset.toggleSecret);
            if (input) {
                updateSecretButton(button, input);
            }

            button.addEventListener("click", () => {
                const input = document.getElementById(button.dataset.toggleSecret);
                if (!input) {
                    return;
                }
                setSecretVisible(input, input.type === "password");
            });
        });

        if (!user) {
            setMessage("passwordMessage", "请先登录后查看用户信息", true);
            return;
        }

        await loadProfile(user).catch((error) => {
            setMessage(
                "passwordMessage",
                error.message === "Failed to fetch" ? "无法连接后端服务，已显示登录信息" : error.message,
                true
            );
        });
    }

    document.addEventListener("DOMContentLoaded", boot);
})();
