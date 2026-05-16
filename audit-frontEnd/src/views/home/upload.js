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

    async function savePendingFiles(event) {
        event.preventDefault();
        collectPendingKeywords();

        const pendingList = document.getElementById("pendingList");
        const saveUploads = document.getElementById("saveUploads");
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
        saveUploads.textContent = "上传中...";

        try {
            const result = await apiForm("/home/files/upload", formData);
            const uploadedFiles = result.files || [];
            state.pendingFiles = [];
            renderPendingFiles();
            pendingList.innerHTML = `
                <div class="empty-row">
                    上传成功，已保存 ${uploadedFiles.length} 个文件。可继续选择文件上传，或前往首页查看文件列表。
                </div>
            `;
            window.alert(`上传成功，已保存 ${uploadedFiles.length} 个文件。`);
        } catch (error) {
            pendingList.innerHTML = `<div class="empty-row">${escapeHtml(error.message)}</div>`;
        } finally {
            saveUploads.disabled = false;
            saveUploads.textContent = "保存到文件列表";
        }
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
    }

    document.addEventListener("DOMContentLoaded", boot);
})();
