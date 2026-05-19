(function() {
    const state = {
        pendingFiles: []
    };

    function getAuditApp() {
        return window.AuditApp || {};
    }

    function fallbackEscapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function fallbackFormatSize(size) {
        if (size < 1024) {
            return `${size} B`;
        }

        if (size < 1024 * 1024) {
            return `${(size / 1024).toFixed(1)} KB`;
        }

        return `${(size / 1024 / 1024).toFixed(1)} MB`;
    }

    function escapeHtml(value) {
        return getAuditApp().escapeHtml?.(value) || fallbackEscapeHtml(value);
    }

    function formatSize(size) {
        return getAuditApp().formatSize?.(size) || fallbackFormatSize(size);
    }

    function getUserId() {
        return getAuditApp().userId?.() || "";
    }

    function makeFileKey(file) {
        return `${file.name}::${file.size}::${file.lastModified}`;
    }

    function renderPendingFiles() {
        const pendingList = document.getElementById("pendingList");
        if (!pendingList) {
            return;
        }

        if (!state.pendingFiles.length) {
            pendingList.innerHTML = "";
            return;
        }

        pendingList.innerHTML = state.pendingFiles.map((item, index) => `
            <div class="pending-item">
                <div class="pending-name">
                    <strong>${escapeHtml(item.file.name)}</strong>
                    <span>${formatSize(item.file.size)}</span>
                </div>
                <input type="text" data-pending-index="${index}" placeholder="输入关键词，多个关键词用逗号分隔" value="${escapeHtml(item.keywords)}">
                <button class="soft-button pending-remove" type="button" data-remove-index="${index}">移除</button>
            </div>
        `).join("");
    }

    function collectPendingKeywords() {
        document.querySelectorAll("[data-pending-index]").forEach((input) => {
            const index = Number(input.dataset.pendingIndex);
            if (state.pendingFiles[index]) {
                state.pendingFiles[index].keywords = input.value;
            }
        });
    }

    function removePendingFile(index) {
        state.pendingFiles.splice(index, 1);
        renderPendingFiles();
    }

    async function submitPendingFiles(event, options) {
        event.preventDefault();
        collectPendingKeywords();

        const pendingList = document.getElementById("pendingList");
        const saveUploads = document.getElementById("saveUploads");
        const appendUploads = document.getElementById("appendUploads");
        const actionButton = options.buttonId ? document.getElementById(options.buttonId) : saveUploads;
        const { apiForm } = getAuditApp();
        const userId = getUserId();

        if (!userId) {
            pendingList.innerHTML = `<div class="empty-row">请先登录后上传文件</div>`;
            return;
        }

        if (!apiForm) {
            pendingList.innerHTML = `<div class="empty-row">页面脚本未完成加载，请刷新后重试</div>`;
            return;
        }

        const validItems = state.pendingFiles.filter((item) => item.keywords.trim());
        if (!validItems.length) {
            pendingList.innerHTML = `<div class="empty-row">请为至少一个文件填写关键词</div>`;
            return;
        }

        const formData = new FormData();
        formData.append("user_id", userId);
        validItems.forEach((item) => {
            formData.append("files", item.file);
            formData.append("keywords", item.keywords);
        });

        saveUploads.disabled = true;
        appendUploads.disabled = true;
        actionButton.textContent = options.busyText;

        try {
            const result = await apiForm(options.path, formData);
            const uploadedFiles = result.files || [];
            state.pendingFiles = [];
            renderPendingFiles();
            pendingList.innerHTML = `
                <div class="empty-row">
                    ${options.successText(uploadedFiles.length)}
                </div>
            `;
            window.alert(options.alertText(uploadedFiles.length));
        } catch (error) {
            pendingList.innerHTML = `<div class="empty-row">${escapeHtml(error.message)}</div>`;
        } finally {
            saveUploads.disabled = false;
            appendUploads.disabled = false;
            saveUploads.textContent = "保存到文件列表";
            appendUploads.textContent = "新增文件";
        }
    }

    function savePendingFiles(event) {
        return submitPendingFiles(event, {
            path: "/home/files/upload",
            buttonId: "saveUploads",
            busyText: "上传中...",
            successText: (count) => `上传成功，已保存 ${count} 个文件。可继续选择文件上传，或前往首页查看文件列表。`,
            alertText: (count) => `上传成功，已保存 ${count} 个文件。`
        });
    }

    function appendPendingFiles(event) {
        return submitPendingFiles(event, {
            path: "/home/files/append",
            buttonId: "appendUploads",
            busyText: "新增中...",
            successText: (count) => `新增成功，已追加 ${count} 个文件并更新安全索引、RAL 与验证器。`,
            alertText: (count) => `新增成功，已追加 ${count} 个文件。`
        });
    }

    function handleFileChange(event) {
        const existingKeys = new Set(state.pendingFiles.map((item) => item.fileKey));
        const nextFiles = Array.from(event.target.files || []);

        nextFiles.forEach((file) => {
            const fileKey = makeFileKey(file);
            if (!existingKeys.has(fileKey)) {
                state.pendingFiles.push({
                    file,
                    fileKey,
                    keywords: ""
                });
                existingKeys.add(fileKey);
            }
        });

        event.target.value = "";
        renderPendingFiles();
    }

    function boot() {
        const { setupShell } = getAuditApp();
        const fileInput = document.getElementById("fileInput");
        const pendingList = document.getElementById("pendingList");
        const saveUploads = document.getElementById("saveUploads");
        const appendUploads = document.getElementById("appendUploads");

        if (setupShell) {
            setupShell("upload");
        }

        fileInput?.addEventListener("change", handleFileChange);
        pendingList?.addEventListener("input", collectPendingKeywords);
        pendingList?.addEventListener("click", (event) => {
            const removeButton = event.target.closest("[data-remove-index]");
            if (!removeButton) {
                return;
            }

            removePendingFile(Number(removeButton.dataset.removeIndex));
        });
        saveUploads?.addEventListener("click", savePendingFiles);
        appendUploads?.addEventListener("click", appendPendingFiles);
    }

    document.addEventListener("DOMContentLoaded", boot);
})();
