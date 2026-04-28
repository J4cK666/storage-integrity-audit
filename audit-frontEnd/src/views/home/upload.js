const {
    apiForm,
    escapeHtml,
    formatSize,
    setupShell,
    userId
} = window.AuditApp;

const state = {
    pendingFiles: []
};

const fileInput = document.getElementById("fileInput");
const pendingList = document.getElementById("pendingList");
const saveUploads = document.getElementById("saveUploads");

function renderPendingFiles() {
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
        </div>
    `).join("");
}

function collectPendingKeywords() {
    document.querySelectorAll("[data-pending-index]").forEach((input) => {
        state.pendingFiles[Number(input.dataset.pendingIndex)].keywords = input.value;
    });
}

async function savePendingFiles() {
    collectPendingKeywords();

    const validItems = state.pendingFiles.filter((item) => item.keywords.trim());
    if (!validItems.length) {
        pendingList.innerHTML = `<div class="empty-row">请为至少一个文件填写关键词</div>`;
        return;
    }

    const formData = new FormData();
    formData.append("user_id", userId());
    validItems.forEach((item) => {
        formData.append("files", item.file);
        formData.append("keywords", item.keywords);
    });

    saveUploads.disabled = true;
    saveUploads.textContent = "上传中...";

    try {
        await apiForm("/home/files/upload", formData);
        window.location.href = "./home.html";
    } catch (error) {
        pendingList.innerHTML = `<div class="empty-row">${escapeHtml(error.message)}</div>`;
    } finally {
        saveUploads.disabled = false;
        saveUploads.textContent = "保存到文件列表";
    }
}

function boot() {
    if (!setupShell("upload")) {
        return;
    }

    fileInput.addEventListener("change", () => {
        state.pendingFiles = Array.from(fileInput.files).map((file) => ({
            file,
            keywords: ""
        }));
        renderPendingFiles();
    });

    pendingList.addEventListener("input", collectPendingKeywords);
    saveUploads.addEventListener("click", savePendingFiles);
}

boot();
