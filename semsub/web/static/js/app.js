/**
 * SemSub Web GUI - Shared JavaScript utilities
 */

// API helpers
async function apiGet(path) {
    const response = await fetch('/api' + path);
    if (!response.ok) {
        let msg = `HTTP ${response.status}`;
        try {
            const data = await response.json();
            msg = data.detail || data.message || msg;
        } catch {}
        throw new Error(msg);
    }
    return response.json();
}

async function apiPost(path, params) {
    let url = '/api' + path;
    if (params) {
        url += '?' + params.toString();
    }
    const response = await fetch(url, { method: 'POST' });
    if (!response.ok) {
        let msg = `HTTP ${response.status}`;
        try {
            const data = await response.json();
            msg = data.detail || data.message || msg;
        } catch {}
        throw new Error(msg);
    }
    return response.json();
}

async function apiPostJson(path, body) {
    const response = await fetch('/api' + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        let msg = `HTTP ${response.status}`;
        try {
            const data = await response.json();
            msg = data.detail || data.message || msg;
        } catch {}
        throw new Error(msg);
    }
    return response.json();
}

// Toast notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Format bytes
function formatBytes(bytes) {
    if (bytes == null || bytes === undefined) return '';
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
