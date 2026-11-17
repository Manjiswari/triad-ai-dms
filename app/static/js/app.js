const API_BASE = '/api';

function getToken() {
    return localStorage.getItem('dms_token') || '';
}

function setToken(token) {
    if (token) {
        localStorage.setItem('dms_token', token);
    } else {
        localStorage.removeItem('dms_token');
    }
}

function getCurrentUser() {
    try {
        const u = localStorage.getItem('dms_user');
        return u ? JSON.parse(u) : null;
    } catch {
        return null;
    }
}

function setCurrentUser(user) {
    if (user) {
        localStorage.setItem('dms_user', JSON.stringify(user));
    } else {
        localStorage.removeItem('dms_user');
    }
}

async function apiFetch(endpoint, options = {}) {
    const headers = options.headers || {};
    const token = getToken();
    
    if (token && !headers['Authorization']) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }

    const config = { ...options, headers };

    try {
        const res = await fetch(`${API_BASE}${endpoint}`, config);
        const data = await res.json().catch(() => null);
        return { ok: res.ok, status: res.status, data };
    } catch (err) {
        console.error(`API Fetch Error on ${endpoint}:`, err);
        return { ok: false, status: 0, data: { error: err.message || 'Network connection failed' } };
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    const colorClasses = {
        success: 'bg-emerald-600 text-white',
        error: 'bg-red-600 text-white',
        warning: 'bg-amber-600 text-white',
        info: 'bg-slate-800 text-white'
    }[type] || 'bg-slate-800 text-white';

    const iconClasses = {
        success: 'fa-circle-check',
        error: 'fa-circle-xmark',
        warning: 'fa-triangle-exclamation',
        info: 'fa-circle-info'
    }[type] || 'fa-circle-info';

    toast.className = `${colorClasses} px-4 py-3 rounded-xl shadow-lg flex items-center space-x-3 pointer-events-auto transition-all transform duration-300 ease-out translate-y-2 opacity-0 text-sm max-w-md`;
    toast.innerHTML = `
        <i class="fa-solid ${iconClasses} text-lg"></i>
        <div class="flex-grow font-medium">${message}</div>
        <button onclick="this.parentElement.remove()" class="text-white/80 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
    `;

    container.appendChild(toast);
    setTimeout(() => toast.classList.remove('translate-y-2', 'opacity-0'), 10);
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 4500);
}

async function quickLogin(username, password) {
    const res = await apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
    });

    if (res.ok && res.data && res.data.token) {
        setToken(res.data.token);
        setCurrentUser(res.data.user);
        showToast(`Logged in as ${username} (${res.data.user.division})`, 'success');
        setTimeout(() => window.location.reload(), 400);
    } else {
        showToast(res.data?.error || 'Login failed', 'error');
    }
}

function logout() {
    setToken(null);
    setCurrentUser(null);
    showToast('Signed out', 'info');
    setTimeout(() => window.location.href = '/login', 400);
}

function syncHeaderAuthState() {
    const user = getCurrentUser();
    const loggedInEl = document.getElementById('auth-logged-in');
    const loggedOutEl = document.getElementById('auth-logged-out');

    if (user && user.username) {
        if (loggedInEl) loggedInEl.classList.remove('hidden');
        if (loggedOutEl) loggedOutEl.classList.add('hidden');

        const uEl = document.getElementById('current-username');
        const dEl = document.getElementById('current-division');
        const rEl = document.getElementById('current-role');
        if (uEl) uEl.textContent = user.username;
        if (dEl) dEl.textContent = user.division || 'No Division';
        if (rEl) rEl.textContent = user.role || 'USER';

        checkPendingRequestsCount();
    } else {
        if (loggedInEl) loggedInEl.classList.add('hidden');
        if (loggedOutEl) loggedOutEl.classList.remove('hidden');
    }

    const path = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
    if (path === '/') document.getElementById('nav-dashboard')?.classList.add('active');
    else if (path.startsWith('/search')) document.getElementById('nav-search')?.classList.add('active');
    else if (path.startsWith('/requests')) document.getElementById('nav-requests')?.classList.add('active');
    else if (path.startsWith('/admin')) document.getElementById('nav-admin')?.classList.add('active');
}

async function checkPendingRequestsCount() {
    const user = getCurrentUser();
    if (!user) return;
    const res = await apiFetch('/access/requests?type=incoming');
    if (res.ok && res.data && res.data.requests) {
        const pendingCount = res.data.requests.filter(r => r.status === 'pending').length;
        const badge = document.getElementById('requests-badge');
        if (badge) {
            if (pendingCount > 0) {
                badge.textContent = pendingCount;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    syncHeaderAuthState();

    const switchBtn = document.getElementById('quick-switch-btn');
    const switchDropdown = document.getElementById('quick-switch-dropdown');
    if (switchBtn && switchDropdown) {
        switchBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            switchDropdown.classList.toggle('hidden');
        });
        document.addEventListener('click', () => {
            switchDropdown.classList.add('hidden');
        });
    }

    if (!getCurrentUser() && !window.location.pathname.startsWith('/login')) {
        quickLogin('alice', 'Alice@123');
    }
});
