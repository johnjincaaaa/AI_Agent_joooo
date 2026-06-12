// ==============================
// 输入框粘贴图片
// ==============================

const imagePreviewBar = document.getElementById('imagePreviewBar');
const pasteTarget = document.getElementById('userInput');

/** @type {{id: string, file: File, previewUrl: string}[]} */
let pendingImages = [];

function buildAuthHeadersForUpload() {
    const headers = {};
    const token = localStorage.getItem('token');
    if (token && token !== 'null') {
        headers['Authorization'] = 'Bearer ' + token;
    }
    return headers;
}

function hasPendingImages() {
    return pendingImages.length > 0;
}

function renderImagePreviews() {
    if (!imagePreviewBar) return;

    if (!pendingImages.length) {
        imagePreviewBar.hidden = true;
        imagePreviewBar.innerHTML = '';
        return;
    }

    imagePreviewBar.hidden = false;
    imagePreviewBar.innerHTML = '';

    pendingImages.forEach(item => {
        const wrap = document.createElement('div');
        wrap.className = 'image-preview-item';
        wrap.innerHTML = `
            <img src="${item.previewUrl}" alt="待发送图片">
            <button type="button" class="image-preview-remove" aria-label="移除图片" data-id="${item.id}">×</button>
        `;
        wrap.querySelector('.image-preview-remove').addEventListener('click', () => {
            removePendingImage(item.id);
        });
        imagePreviewBar.appendChild(wrap);
    });
}

function addPendingImage(file) {
    if (!file || !file.type.startsWith('image/')) return;

    const id = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    pendingImages.push({
        id,
        file,
        previewUrl: URL.createObjectURL(file),
    });
    renderImagePreviews();

    if (typeof enableSkill === 'function') {
        enableSkill('image_parsing');
    }
}

function removePendingImage(id) {
    const index = pendingImages.findIndex(item => item.id === id);
    if (index === -1) return;
    URL.revokeObjectURL(pendingImages[index].previewUrl);
    pendingImages.splice(index, 1);
    renderImagePreviews();
}

function clearPendingImages() {
    pendingImages.forEach(item => URL.revokeObjectURL(item.previewUrl));
    pendingImages = [];
    renderImagePreviews();
}

async function uploadPendingImages() {
    if (!pendingImages.length) {
        return { paths: [], urls: [] };
    }

    const paths = [];
    const urls = [];

    for (const item of pendingImages) {
        const formData = new FormData();
        formData.append('file', item.file, item.file.name || 'pasted-image.png');

        const res = await fetch(`${config.API_BASE_URL}/ai/upload-image`, {
            method: 'POST',
            headers: buildAuthHeadersForUpload(),
            body: formData,
        });

        if (res.status === 429) {
            throw new Error('RATE_LIMIT');
        }
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(parseApiErrorMessage(errData, '图片上传失败'));
        }

        const data = await res.json();
        paths.push(data.path);
        urls.push(data.url);
    }

    return { paths, urls };
}

function buildDisplayMessage(text, imageUrls) {
    const parts = [];
    imageUrls.forEach(url => {
        parts.push(`![图片](${url})`);
    });
    if (text) {
        parts.push(text);
    }
    if (!parts.length) {
        return '请分析这张图片';
    }
    return parts.join('\n\n');
}

function handleImagePaste(event) {
    const items = event.clipboardData?.items;
    if (!items) return;

    const imageFiles = [];
    for (const item of items) {
        if (item.type.startsWith('image/')) {
            const file = item.getAsFile();
            if (file) imageFiles.push(file);
        }
    }

    if (!imageFiles.length) return;

    event.preventDefault();
    imageFiles.forEach(addPendingImage);
}

if (pasteTarget) {
    pasteTarget.addEventListener('paste', handleImagePaste);
}

window.hasPendingImages = hasPendingImages;
window.uploadPendingImages = uploadPendingImages;
window.clearPendingImages = clearPendingImages;
window.buildDisplayMessage = buildDisplayMessage;
