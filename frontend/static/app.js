// =============================================
// API CONFIGURATION
// =============================================
const API_URL = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
    ? window.location.origin 
    : 'http://127.0.0.1:8000';

// =============================================
// GLOBAL STATE
// =============================================
let state = {
    username: sessionStorage.getItem('sop_username') || null,
    role: sessionStorage.getItem('sop_role') || null,
    displayName: sessionStorage.getItem('sop_display_name') || null,
    designation: sessionStorage.getItem('sop_designation') || null,
    simulatedRole: sessionStorage.getItem('sop_sim_role') || null,
    chatHistory: [],
    documents: [],
    analyticsStats: {},
    feedbackLogs: []
};

// Staff directory is loaded dynamically from backend GET /staff

// Quick suggestions per role
const suggestions = {
    manager: [
        "📋 Show overall compliance scores",
        "🔍 Which SOP documents are active?",
        "⚠️ Recent negative feedback audits",
        "🔧 How are document versions tracked?"
    ],
    kitchen: [
        "🍗 Correct cooking temperature for poultry",
        "🧼 Hand washing frequency rules",
        "🧹 Policy for sanitizing work surfaces",
        "📅 Kitchen cleaning schedule"
    ],
    server: [
        "🥤 Protocol for handling service spills",
        "👔 Staff dress code & hygiene",
        "💳 POS terminal checklists",
        "🛎️ Food presentation standards"
    ]
};

// Chart instances
let satisfactionChart = null;
let timelineChart = null;

// Upload file
let selectedUploadFile = null;

// =============================================
// INIT
// =============================================
document.addEventListener('DOMContentLoaded', () => {
    initParticles();
    initApp();
    setupEventListeners();
});

function initApp() {
    if (state.username && state.role) {
        if (!state.simulatedRole) state.simulatedRole = state.role;
        enterDashboard();
    } else {
        showLoginScreen();
    }
}

// =============================================
// PARTICLES CANVAS (Login Screen)
// =============================================
function initParticles() {
    const canvas = document.getElementById('particles-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let particles = [];
    const PARTICLE_COUNT = 55;

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    class Particle {
        constructor() {
            this.reset();
        }
        reset() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.vx = (Math.random() - 0.5) * 0.15; // Slower drifting speed (was 0.4)
            this.vy = (Math.random() - 0.5) * 0.15;
            this.radius = Math.random() * 1.5 + 0.6; // Slightly larger for better visibility
            this.opacity = Math.random() * 0.22 + 0.08; // Clear professional opacity
            // Cyan-Indigo theme
            this.color = Math.random() > 0.5 ? 'rgba(129, 140, 248, ' : 'rgba(34, 211, 238, ';
        }
        update() {
            this.x += this.vx;
            this.y += this.vy;
            if (this.x < 0 || this.x > canvas.width) this.vx *= -1;
            if (this.y < 0 || this.y > canvas.height) this.vy *= -1;
        }
        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = this.color + this.opacity + ')';
            ctx.fill();
        }
    }

    for (let i = 0; i < PARTICLE_COUNT; i++) {
        particles.push(new Particle());
    }

    function drawConnections() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 130) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(129, 140, 248, ${0.04 * (1 - dist / 130)})`; // Soft faint connections
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }
    }

    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach(p => { p.update(); p.draw(); });
        drawConnections();
        requestAnimationFrame(animate);
    }
    animate();
}


// =============================================
// EVENT LISTENERS
// =============================================
function setupEventListeners() {
    // Password toggle
    const pwdToggle = document.getElementById('toggle-password');
    if (pwdToggle) {
        pwdToggle.addEventListener('click', () => {
            const pwdInput = document.getElementById('password');
            const icon = pwdToggle.querySelector('i');
            if (pwdInput.type === 'password') {
                pwdInput.type = 'text';
                icon.className = 'fa-solid fa-eye-slash';
            } else {
                pwdInput.type = 'password';
                icon.className = 'fa-solid fa-eye';
            }
        });
    }

    // Login form
    const loginForm = document.getElementById('login-form');
    if (loginForm) loginForm.addEventListener('submit', handleLogin);

    // Chat form
    const chatForm = document.getElementById('chat-input-form');
    if (chatForm) chatForm.addEventListener('submit', handleChatSubmit);

    // Role simulator
    document.querySelectorAll('.sim-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.sim-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            simulateRoleScope(btn.getAttribute('data-sim'));
        });
    });

    // Dropzone
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('upload-file-input');
    if (dropzone && fileInput) {
        dropzone.addEventListener('click', () => fileInput.click());
        dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
        dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
        dropzone.addEventListener('drop', e => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) handleFileSelect(e.dataTransfer.files[0]);
        });
        fileInput.addEventListener('change', e => {
            if (e.target.files.length > 0) handleFileSelect(e.target.files[0]);
        });
    }

    // Upload form
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) uploadForm.addEventListener('submit', handleDocUpload);

    // Danger action confirmation locks
    const confirmDocs = document.getElementById('confirm-erase-docs');
    const btnDocs = document.getElementById('btn-erase-docs');
    if (confirmDocs && btnDocs) {
        confirmDocs.addEventListener('change', e => { btnDocs.disabled = !e.target.checked; });
    }
    const confirmLogs = document.getElementById('confirm-erase-logs');
    const btnLogs = document.getElementById('btn-erase-logs');
    if (confirmLogs && btnLogs) {
        confirmLogs.addEventListener('change', e => { btnLogs.disabled = !e.target.checked; });
    }

    // Edit Profile triggers
    const editProfileBtn = document.getElementById('btn-edit-profile');
    if (editProfileBtn) {
        editProfileBtn.addEventListener('click', openProfileModal);
    }
    const closeProfileModalBtn = document.getElementById('btn-close-profile-modal');
    if (closeProfileModalBtn) {
        closeProfileModalBtn.addEventListener('click', closeProfileModal);
    }
    const profileForm = document.getElementById('profile-edit-form');
    if (profileForm) {
        profileForm.addEventListener('submit', handleProfileUpdate);
    }
}

// =============================================
// TOAST NOTIFICATIONS
// =============================================
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    let iconClass = 'fa-solid fa-circle-info info';
    if (type === 'success') iconClass = 'fa-solid fa-circle-check success';
    if (type === 'error') iconClass = 'fa-solid fa-triangle-exclamation error';
    toast.innerHTML = `<i class="${iconClass}"></i><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// =============================================
// LOGIN
// =============================================
async function handleLogin(e) {
    e.preventDefault();
    const userVal = document.getElementById('username').value.trim();
    const passVal = document.getElementById('password').value;
    const errorBox = document.getElementById('login-error');
    const errorMsg = document.getElementById('login-error-msg');
    const loginBtn = document.getElementById('btn-login-submit');

    errorBox.classList.add('hidden');
    loginBtn.disabled = true;
    loginBtn.querySelector('.btn-text').innerText = 'Authenticating...';
    loginBtn.querySelector('.btn-icon').classList.add('hidden');
    loginBtn.querySelector('.btn-loader').classList.remove('hidden');

    const formData = new FormData();
    formData.append('username', userVal);
    formData.append('password', passVal);

    try {
        const res = await fetch(`${API_URL}/login`, { method: 'POST', body: formData });
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                state.username = data.username;
                state.role = data.role;
                state.displayName = data.display_name || data.username;
                state.designation = data.designation || 'Staff';
                state.simulatedRole = data.role;

                sessionStorage.setItem('sop_username', data.username);
                sessionStorage.setItem('sop_role', data.role);
                sessionStorage.setItem('sop_display_name', state.displayName);
                sessionStorage.setItem('sop_designation', state.designation);
                sessionStorage.setItem('sop_sim_role', data.role);

                showToast(`Welcome, ${state.displayName}!`, 'success');
                enterDashboard();
            } else {
                showAuthError(data.message || 'Invalid username or password.');
            }
        } else {
            showAuthError('Server error. Please ensure backend is running.');
        }
    } catch (err) {
        showAuthError('Cannot reach server. Is the backend running?');
        console.error(err);
    } finally {
        loginBtn.disabled = false;
        loginBtn.querySelector('.btn-text').innerText = 'Sign In';
        loginBtn.querySelector('.btn-icon').classList.remove('hidden');
        loginBtn.querySelector('.btn-loader').classList.add('hidden');
    }
}

function showAuthError(msg) {
    const card = document.querySelector('.login-card');
    const errorBox = document.getElementById('login-error');
    const errorMsg = document.getElementById('login-error-msg');
    errorMsg.innerText = msg;
    errorBox.classList.remove('hidden');
    card.classList.add('shaking');
    setTimeout(() => card.classList.remove('shaking'), 500);
}

function showLoginScreen() {
    document.getElementById('login-screen').classList.add('active');
    document.getElementById('app-shell').classList.add('hidden');
    const form = document.getElementById('login-form');
    if (form) form.reset();
}

// =============================================
// DASHBOARD SETUP
// =============================================
async function enterDashboard() {
    document.getElementById('login-screen').classList.remove('active');
    document.getElementById('app-shell').classList.remove('hidden');

    // Set user info
    document.getElementById('sidebar-display-name').innerText = state.displayName || state.username;
    document.getElementById('sidebar-designation').innerText = state.designation || '';
    
    const badge = document.getElementById('sidebar-role-badge');
    badge.innerText = state.role.toUpperCase();
    badge.className = `badge badge-${state.role.toLowerCase()}`;

    // Manager-only features
    const navAdmin = document.getElementById('nav-admin-tab');
    const roleSim = document.getElementById('role-simulator');
    const staffDir = document.getElementById('staff-directory');

    if (state.role.toLowerCase() === 'manager') {
        navAdmin.classList.remove('hidden');
        roleSim.classList.remove('hidden');
        staffDir.classList.remove('hidden');
        renderStaffDirectory();

        const activeBtn = document.querySelector(`.sim-btn[data-sim="${state.simulatedRole}"]`);
        if (activeBtn) {
            document.querySelectorAll('.sim-btn').forEach(b => b.classList.remove('active'));
            activeBtn.classList.add('active');
        }
    } else {
        navAdmin.classList.add('hidden');
        roleSim.classList.add('hidden');
        staffDir.classList.add('hidden');
    }

    switchTab('chat');
    await fetchChatHistory();
}

// Staff directory
async function renderStaffDirectory() {
    const container = document.getElementById('staff-list-container');
    container.innerHTML = '<p class="text-muted" style="font-size:0.72rem; padding:10px 14px;">Loading staff directory...</p>';

    try {
        const res = await fetch(`${API_URL}/staff`);
        if (res.ok) {
            const data = await res.json();
            if (data.success && data.staff) {
                container.innerHTML = '';
                data.staff.forEach((staff, i) => {
                    const card = document.createElement('div');
                    card.className = 'staff-card fade-in-up';
                    card.style.animationDelay = `${i * 0.06}s`;

                    const badgeClass = `badge-${staff.role}`;
                    const iconBg = staff.role === 'manager' ? 'icon-purple' : staff.role === 'kitchen' ? 'icon-green' : 'icon-indigo';

                    card.innerHTML = `
                        <div class="staff-card-icon ${iconBg}"><i class="fa-solid ${staff.icon}"></i></div>
                        <div class="staff-card-info">
                            <strong>${escapeHtml(staff.name)}</strong>
                            <small>${escapeHtml(staff.designation)}</small>
                        </div>
                        <span class="badge ${badgeClass}" style="font-size:0.58rem;">${staff.role}</span>
                    `;
                    container.appendChild(card);
                });
            }
        }
    } catch (e) {
        container.innerHTML = '<p class="text-muted" style="font-size:0.72rem; padding:10px 14px;">Failed to load staff list.</p>';
    }
}

// =============================================
// TAB SWITCHING
// =============================================
window.switchTab = function(tabName) {
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

    const btn = document.getElementById(`nav-${tabName}-tab`);
    const panel = document.getElementById(`tab-${tabName}`);
    if (btn) btn.classList.add('active');
    if (panel) panel.classList.add('active');

    const title = document.getElementById('view-title');
    const subtitle = document.getElementById('view-subtitle');

    if (tabName === 'chat') {
        title.innerText = 'Compliance Assistant';
        subtitle.innerText = `Access Scope: ${state.simulatedRole.toUpperCase()} LEVEL`;
        renderSuggestions();
        scrollToChatBottom();
    } else if (tabName === 'admin') {
        title.innerText = 'Operations Dashboard';
        subtitle.innerText = 'Analytics, Documents & Staff Management';
        loadAdminStats();
    }
}

function simulateRoleScope(simRole) {
    state.simulatedRole = simRole;
    sessionStorage.setItem('sop_sim_role', simRole);
    showToast(`Simulating ${simRole.toUpperCase()} access`, 'info');
    const subtitle = document.getElementById('view-subtitle');
    if (document.getElementById('tab-chat').classList.contains('active')) {
        subtitle.innerText = `Access Scope: ${simRole.toUpperCase()} LEVEL`;
        renderSuggestions();
    }
}

window.logout = function() {
    sessionStorage.clear();
    state = { username: null, role: null, displayName: null, designation: null, simulatedRole: null, chatHistory: [], documents: [], analyticsStats: {}, feedbackLogs: [] };
    showLoginScreen();
    showToast('Logged out', 'success');
}

// =============================================
// CHAT MODULE
// =============================================
async function fetchChatHistory() {
    try {
        const res = await fetch(`${API_URL}/history?username=${encodeURIComponent(state.username)}`);
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                state.chatHistory = data.history;
                renderChatHistory();
            }
        }
    } catch (e) {
        console.error(e);
    }
}

function renderChatHistory() {
    const area = document.getElementById('chat-messages');
    area.innerHTML = `
        <div class="chat-message assistant fade-in-up">
            <div class="message-avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="message-content">
                <p>👋 Welcome to the <strong>Restaurant Compliance Assistant</strong>.</p>
                <p>Ask me any question about Standard Operating Procedures — food safety, hygiene, service protocols, and more.</p>
            </div>
        </div>
    `;
    state.chatHistory.forEach(msg => {
        appendChatBubble('user', msg.question);
        appendChatBubble('assistant', msg.answer, {
            id: msg.id,
            timestamp: msg.timestamp,
            citations: msg.citations,
            role: msg.role
        });
    });
    scrollToChatBottom();
}

function appendChatBubble(sender, text, metadata = null) {
    const area = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    msg.className = `chat-message ${sender} fade-in-up`;

    if (sender === 'user') {
        msg.innerHTML = `
            <div class="message-avatar"><i class="fa-solid fa-user"></i></div>
            <div class="message-content"><p>${escapeHtml(text)}</p></div>
        `;
    } else {
        let formattedText = formatMarkdown(text);
        let btsHtml = '';
        if (metadata) {
            btsHtml = `
                <div class="bts-expander" id="bts-${metadata.id}">
                    <div class="bts-header" onclick="toggleBtsAccordion(${metadata.id})">
                        <span>🔍 RAG Metadata</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </div>
                    <div class="bts-content">
                        <p>🏷️ <b>Role Scope:</b> <code>${escapeHtml(metadata.role.toUpperCase())}</code></p>
                        <p>⏱️ <b>Audit ID:</b> <code>${metadata.id}</code></p>
                        <p>📅 <b>Logged:</b> ${metadata.timestamp.substring(0,19).replace('T',' ')}</p>
                    </div>
                </div>
            `;
        }

        let ratingHtml = '';
        if (metadata?.id) {
            ratingHtml = `
                <div class="rating-panel" id="rate-panel-${metadata.id}">
                    <button class="rating-btn" onclick="submitRating(${metadata.id}, 1)"><i class="fa-solid fa-thumbs-up"></i> Good</button>
                    <button class="rating-btn" onclick="submitRating(${metadata.id}, -1)"><i class="fa-solid fa-thumbs-down"></i> Poor</button>
                </div>
                <div class="feedback-comments-drawer hidden" id="comments-drawer-${metadata.id}">
                    <input type="text" id="comment-input-${metadata.id}" placeholder="Comments (optional)..." />
                    <button class="btn btn-secondary btn-small" onclick="submitNegativeComment(${metadata.id})">Submit</button>
                </div>
            `;
        }

        msg.innerHTML = `
            <div class="message-avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="message-content">
                <div>${formattedText}</div>
                ${btsHtml}
                ${ratingHtml}
            </div>
        `;
    }
    area.appendChild(msg);
}

window.toggleBtsAccordion = function(id) {
    const el = document.getElementById(`bts-${id}`);
    if (el) el.classList.toggle('open');
};

window.submitRating = async function(chatId, rating) {
    const panel = document.getElementById(`rate-panel-${chatId}`);
    if (rating === 1) {
        try {
            const fd = new FormData();
            fd.append('chat_id', chatId);
            fd.append('rating', 1);
            fd.append('comments', 'Good answer');
            const res = await fetch(`${API_URL}/feedback`, { method: 'POST', body: fd });
            if (res.ok) {
                showToast('Thank you!', 'success');
                panel.innerHTML = `<span style="font-size:0.72rem; color:var(--accent-green); font-style:italic;"><i class="fa-solid fa-circle-check"></i> Rated Good</span>`;
            }
        } catch (e) { showToast('Rating failed', 'error'); }
    } else {
        const drawer = document.getElementById(`comments-drawer-${chatId}`);
        drawer.classList.remove('hidden');
        panel.querySelectorAll('button').forEach(b => b.disabled = true);
    }
};

window.submitNegativeComment = async function(chatId) {
    const input = document.getElementById(`comment-input-${chatId}`);
    const val = input.value.trim();
    const panel = document.getElementById(`rate-panel-${chatId}`);
    const drawer = document.getElementById(`comments-drawer-${chatId}`);
    
    // Comments are optional
    const finalComment = val || 'Poor rating (no comment)';
    
    try {
        const fd = new FormData();
        fd.append('chat_id', chatId);
        fd.append('rating', -1);
        fd.append('comments', finalComment);
        const res = await fetch(`${API_URL}/feedback`, { method: 'POST', body: fd });
        if (res.ok) {
            showToast('Feedback submitted', 'success');
            panel.innerHTML = `<span style="font-size:0.72rem; color:var(--accent-danger); font-style:italic;"><i class="fa-solid fa-circle-check"></i> Rated Poor</span>`;
            drawer.classList.add('hidden');
        }
    } catch (e) { showToast('Submission failed', 'error'); }
};

function renderSuggestions() {
    const container = document.getElementById('suggestions-container');
    container.innerHTML = '';
    const pills = suggestions[state.simulatedRole?.toLowerCase()] || suggestions.server;
    pills.forEach(sugg => {
        const span = document.createElement('span');
        span.className = 'suggestion-pill';
        span.innerText = sugg;
        span.addEventListener('click', () => {
            let q = sugg.replace(/[\uE000-\uF8FF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|[\u2011-\u26FF]|\uD83E[\uDD10-\uDDFF]/g, "").trim();
            document.getElementById('chat-input').value = q;
            document.getElementById('chat-input-form').dispatchEvent(new Event('submit'));
        });
        container.appendChild(span);
    });
}

function scrollToChatBottom() {
    const area = document.getElementById('chat-messages');
    area.scrollTop = area.scrollHeight;
}

async function handleChatSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const prompt = input.value.trim();
    if (!prompt) return;
    input.value = '';

    appendChatBubble('user', prompt);
    scrollToChatBottom();

    // Typing indicator
    const area = document.getElementById('chat-messages');
    const loader = document.createElement('div');
    loader.className = 'chat-message assistant fade-in-up';
    loader.id = 'loading-bot';
    loader.innerHTML = `
        <div class="message-avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="message-content">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    area.appendChild(loader);
    scrollToChatBottom();

    const fd = new FormData();
    fd.append('question', prompt);
    fd.append('role', state.simulatedRole);
    fd.append('username', state.username);

    try {
        const res = await fetch(`${API_URL}/ask`, { method: 'POST', body: fd });
        loader.remove();
        if (res.ok) {
            await fetchChatHistory();
            showToast('Answer retrieved!', 'success');
        } else {
            appendChatBubble('assistant', 'Error querying the compliance engine.');
            showToast('Query error', 'error');
        }
    } catch (err) {
        loader.remove();
        appendChatBubble('assistant', 'Connection lost. Is the backend running?');
        showToast('Connection failed', 'error');
    }
}

window.clearChat = async function() {
    if (!confirm('Clear your chat history? This cannot be undone.')) return;
    try {
        const fd = new FormData();
        fd.append('username', state.username);
        const res = await fetch(`${API_URL}/clear_history`, { method: 'POST', body: fd });
        if (res.ok) {
            state.chatHistory = [];
            renderChatHistory();
            showToast('Chat cleared!', 'success');
        }
    } catch (e) { showToast('Failed to clear', 'error'); }
}

window.exportChatAudit = function() {
    if (!state.chatHistory.length) { showToast('No data to export', 'error'); return; }
    let csv = 'data:text/csv;charset=utf-8,';
    csv += 'ID,User,Role,Timestamp,Question,Answer,Citations\n';
    state.chatHistory.forEach(m => {
        const cit = m.citations ? m.citations.join('; ') : '';
        csv += [m.id, `"${m.username}"`, `"${m.role}"`, m.timestamp.substring(0,19).replace('T',' '), `"${m.question.replace(/"/g,'""')}"`, `"${m.answer.replace(/"/g,'""')}"`, `"${cit}"`].join(',') + '\n';
    });
    const link = document.createElement('a');
    link.setAttribute('href', encodeURI(csv));
    link.setAttribute('download', `sop_audit_${state.username}_${new Date().toISOString().substring(0,10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('CSV downloaded', 'success');
}

// =============================================
// ADMIN CONSOLE
// =============================================
async function loadAdminStats() {
    try {
        const res = await fetch(`${API_URL}/analytics?role=${encodeURIComponent(state.role)}`);
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                state.analyticsStats = data.stats;
                state.feedbackLogs = data.logs;
                updateKpiCards();
                renderCharts();
                renderFeedbackLogs();
                await fetchDocuments();
            }
        }
    } catch (e) {
        showToast('Analytics unavailable', 'error');
    }
}

function updateKpiCards() {
    const s = state.analyticsStats;
    document.getElementById('kpi-docs-count').innerText = s.total_docs || 0;
    document.getElementById('kpi-chats-count').innerText = s.total_chats || 0;
    document.getElementById('kpi-feedback-count').innerText = s.total_feedback || 0;
    let score = s.total_feedback > 0 ? Math.round((s.positive_feedback / s.total_feedback) * 100) : 0;
    const el = document.getElementById('kpi-quality-score');
    el.innerText = `${score}%`;
    el.style.color = score >= 80 ? 'var(--accent-green)' : score >= 50 ? 'var(--accent-orange)' : 'var(--accent-danger)';
}

function renderCharts() {
    const s = state.analyticsStats;
    const logs = state.feedbackLogs;

    // Bar chart
    const ctxBar = document.getElementById('satisfaction-chart').getContext('2d');
    if (satisfactionChart) satisfactionChart.destroy();
    satisfactionChart = new Chart(ctxBar, {
        type: 'bar',
        data: {
            labels: ['Good 👍', 'Poor 👎'],
            datasets: [{
                data: [s.positive_feedback || 0, s.negative_feedback || 0],
                backgroundColor: ['rgba(52,211,153,0.4)', 'rgba(248,113,113,0.4)'],
                borderColor: ['#34d399', '#f87171'],
                borderWidth: 1.5,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, ticks: { color: '#8b99b0', stepSize: 1 }, grid: { color: 'rgba(255,255,255,0.03)' } },
                x: { ticks: { color: '#8b99b0' }, grid: { display: false } }
            }
        }
    });

    // Line chart
    const ctxLine = document.getElementById('timeline-chart').getContext('2d');
    if (timelineChart) timelineChart.destroy();
    const dateCounts = {};
    logs.forEach(l => { const d = l.timestamp.substring(0, 10); dateCounts[d] = (dateCounts[d] || 0) + 1; });
    const dates = Object.keys(dateCounts).sort();
    const counts = dates.map(d => dateCounts[d]);

    timelineChart = new Chart(ctxLine, {
        type: 'line',
        data: {
            labels: dates.length ? dates : ['No Data'],
            datasets: [{
                data: counts.length ? counts : [0],
                borderColor: '#818cf8',
                backgroundColor: 'rgba(99,102,241,0.08)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#f472b6',
                pointBorderColor: '#06080e',
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, ticks: { color: '#8b99b0', stepSize: 1 }, grid: { color: 'rgba(255,255,255,0.03)' } },
                x: { ticks: { color: '#8b99b0' }, grid: { display: false } }
            }
        }
    });
}

async function fetchDocuments() {
    try {
        const res = await fetch(`${API_URL}/documents`);
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                state.documents = data.documents;
                renderDocumentsList();
            }
        }
    } catch (e) { showToast('Failed to load docs', 'error'); }
}

function renderDocumentsList() {
    const container = document.getElementById('document-list-container');
    container.innerHTML = '';
    if (!state.documents.length) {
        container.innerHTML = '<p class="text-muted" style="text-align:center; padding:20px;">No documents indexed.</p>';
        return;
    }
    state.documents.forEach((doc, i) => {
        const card = document.createElement('div');
        card.className = 'doc-card';
        card.id = `doc-card-${i}`;
        const isChecked = doc.is_active === 1 ? 'checked' : '';
        const roles = doc.allowed_roles.split(',').map(r => r.trim().toLowerCase());
        card.innerHTML = `
            <div class="doc-card-header" onclick="toggleDocAccordion(${i})">
                <div class="doc-card-title">
                    <i class="fa-solid fa-file-pdf"></i>
                    <span>${escapeHtml(doc.display_name)}</span>
                    <span class="ver">v${doc.version}</span>
                </div>
                <div class="doc-card-header-right">
                    <span class="badge ${doc.is_active ? 'badge-kitchen' : 'badge-server'}" style="font-size:0.6rem;">${doc.is_active ? 'Active' : 'Inactive'}</span>
                    <i class="fa-solid fa-chevron-down collapse-icon"></i>
                </div>
            </div>
            <div class="doc-card-body">
                <div class="doc-meta-row">
                    <div>🗂️ <b>File:</b> <code>${escapeHtml(doc.filename)}</code></div>
                    <div>📅 <b>Uploaded:</b> ${doc.uploaded_at.substring(0,19).replace('T',' ')}</div>
                </div>
                <div class="doc-actions-group">
                    <div class="doc-actions-row">
                        <div class="doc-action-col">
                            <label>RAG State</label>
                            <label class="toggle-switch">
                                <input type="checkbox" ${isChecked} onchange="toggleDocState('${doc.filename}', this.checked)">
                                <span class="slider"></span>
                            </label>
                        </div>
                        <div class="doc-action-col">
                            <label>Permissions</label>
                            <div class="mini-roles-picker">
                                <span class="mini-role-chip ${roles.includes('kitchen') ? 'active' : ''}" onclick="toggleDocRole('${doc.filename}','kitchen',this)">Kitchen</span>
                                <span class="mini-role-chip ${roles.includes('server') ? 'active' : ''}" onclick="toggleDocRole('${doc.filename}','server',this)">Server</span>
                            </div>
                        </div>
                    </div>
                    <div class="doc-actions-row" style="margin-top:6px;">
                        <button class="btn btn-danger btn-small" onclick="deleteDocument('${doc.filename}')"><i class="fa-solid fa-trash-can"></i> Delete</button>
                    </div>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

window.toggleDocAccordion = function(i) {
    const c = document.getElementById(`doc-card-${i}`);
    if (c) c.classList.toggle('open');
};

window.toggleDocState = async function(fn, active) {
    try {
        const fd = new FormData(); fd.append('filename', fn); fd.append('is_active', active);
        const res = await fetch(`${API_URL}/documents/toggle`, { method: 'POST', body: fd });
        if (res.ok) { showToast((await res.json()).message, 'success'); await loadAdminStats(); }
    } catch (e) { showToast('Error', 'error'); }
};

window.toggleDocRole = async function(fn, role, el) {
    const doc = state.documents.find(d => d.filename === fn);
    if (!doc) return;
    let roles = doc.allowed_roles.split(',').map(r => r.trim().toLowerCase());
    if (roles.includes(role)) { roles = roles.filter(r => r !== role); el.classList.remove('active'); }
    else { roles.push(role); el.classList.add('active'); }
    if (!roles.includes('manager')) roles.unshift('manager');
    const rolesStr = roles.join(',');
    try {
        const fd = new FormData(); fd.append('filename', fn); fd.append('allowed_roles', rolesStr);
        const res = await fetch(`${API_URL}/documents/update_roles`, { method: 'POST', body: fd });
        if (res.ok) { showToast('Permissions updated', 'success'); doc.allowed_roles = rolesStr; }
    } catch (e) { showToast('Failed', 'error'); }
};

window.deleteDocument = async function(fn) {
    if (!confirm(`Delete ${fn}?`)) return;
    try {
        const fd = new FormData(); fd.append('filename', fn);
        const res = await fetch(`${API_URL}/documents/delete`, { method: 'POST', body: fd });
        if (res.ok) { showToast('Deleted', 'success'); await loadAdminStats(); }
    } catch (e) { showToast('Failed', 'error'); }
};

function handleFileSelect(file) {
    if (file.type !== 'application/pdf') {
        showToast('Only PDF files accepted', 'error');
        selectedUploadFile = null;
        document.getElementById('selected-file-indicator').classList.add('hidden');
        return;
    }
    selectedUploadFile = file;
    document.getElementById('selected-filename').innerText = file.name;
    document.getElementById('selected-file-indicator').classList.remove('hidden');
    const nameInput = document.getElementById('upload-display-name');
    if (!nameInput.value.trim()) {
        nameInput.value = file.name.replace('.pdf', '').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
}

async function handleDocUpload(e) {
    e.preventDefault();
    const dispName = document.getElementById('upload-display-name').value.trim();
    if (!selectedUploadFile) { showToast('Select a PDF first', 'error'); return; }
    const roles = ['manager'];
    if (document.getElementById('role-kitchen-check').checked) roles.push('kitchen');
    if (document.getElementById('role-server-check').checked) roles.push('server');
    const btn = document.getElementById('btn-upload-submit');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing...';

    const fd = new FormData();
    fd.append('file', selectedUploadFile);
    fd.append('display_name', dispName);
    fd.append('allowed_roles', roles.join(','));

    try {
        const res = await fetch(`${API_URL}/upload`, { method: 'POST', body: fd });
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                showToast('Document indexed!', 'success');
                document.getElementById('upload-form').reset();
                selectedUploadFile = null;
                document.getElementById('selected-file-indicator').classList.add('hidden');
                await loadAdminStats();
            } else { showToast(`Error: ${data.message}`, 'error'); }
        } else { showToast('Upload failed', 'error'); }
    } catch (e) { showToast('Connection error', 'error'); }
    finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-gears"></i> Process & Index Document';
    }
}

window.forceRebuildIndex = async function() {
    showToast('Rebuilding index...', 'info');
    try {
        const res = await fetch(`${API_URL}/index/refresh`, { method: 'POST' });
        if (res.ok) { showToast((await res.json()).message, 'success'); await loadAdminStats(); }
    } catch (e) { showToast('Failed', 'error'); }
};

window.eraseAllDocuments = async function() {
    if (!confirm('⚠️ Erase ALL documents and vector index?')) return;
    try {
        const res = await fetch(`${API_URL}/documents/clear_all`, { method: 'POST' });
        if (res.ok) {
            showToast('Repository erased', 'success');
            document.getElementById('confirm-erase-docs').checked = false;
            document.getElementById('btn-erase-docs').disabled = true;
            await loadAdminStats();
        }
    } catch (e) { showToast('Failed', 'error'); }
};

window.eraseAllLogs = async function() {
    if (!confirm('⚠️ Erase ALL audit logs and feedback?')) return;
    try {
        const fd = new FormData(); fd.append('role', state.role);
        const res = await fetch(`${API_URL}/analytics/clear_logs`, { method: 'POST', body: fd });
        if (res.ok) {
            showToast('Logs cleared', 'success');
            document.getElementById('confirm-erase-logs').checked = false;
            document.getElementById('btn-erase-logs').disabled = true;
            state.chatHistory = [];
            renderChatHistory();
            await loadAdminStats();
        }
    } catch (e) { showToast('Failed', 'error'); }
};

function renderFeedbackLogs() {
    const tbody = document.getElementById('feedback-logs-body');
    tbody.innerHTML = '';
    if (!state.feedbackLogs.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-muted" style="text-align:center;">No logs yet.</td></tr>';
        return;
    }
    state.feedbackLogs.forEach(log => {
        const tr = document.createElement('tr');
        const rc = log.rating === 1 ? 'feedback-rating-good' : 'feedback-rating-poor';
        const rs = log.rating === 1 ? '<i class="fa-solid fa-thumbs-up"></i> Good' : '<i class="fa-solid fa-thumbs-down"></i> Poor';
        const cm = log.comments ? `<span class="feedback-comments-text">"${escapeHtml(log.comments)}"</span>` : '--';
        tr.innerHTML = `
            <td>${escapeHtml(log.username)}</td>
            <td><span class="badge badge-${log.role.toLowerCase()}">${log.role}</span></td>
            <td style="white-space:nowrap;font-size:0.72rem;">${log.timestamp.substring(0,19).replace('T',' ')}</td>
            <td class="feedback-cell-qa">
                <strong>Q:</strong><p>${escapeHtml(log.question)}</p>
                <strong>A:</strong><p style="font-size:0.75rem;opacity:0.9;">${escapeHtml(log.answer)}</p>
            </td>
            <td class="${rc}" style="white-space:nowrap;">${rs}</td>
            <td>${cm}</td>
            <td style="white-space:nowrap; text-align:center;">
                <button class="btn-delete-log" onclick="deleteAuditLog(${log.chat_id})" title="Delete Log Entry">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

async function deleteAuditLog(chatId) {
    if (!confirm('⚠️ Are you sure you want to delete this audit log entry?')) return;
    
    try {
        const fd = new FormData();
        fd.append('chat_id', chatId);
        fd.append('role', state.role);
        
        const res = await fetch(`${API_URL}/analytics/delete_log`, { method: 'POST', body: fd });
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                showToast(data.message, 'success');
                // Reload dashboard analytics logs
                await loadAdminStats();
            } else {
                showToast(data.message || 'Failed to delete log entry', 'error');
            }
        } else {
            showToast('Failed to connect to server', 'error');
        }
    } catch (e) {
        showToast('Error deleting log', 'error');
    }
}

// =============================================
// UTILS
// =============================================
function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;");
}

function formatMarkdown(text) {
    if (!text) return '';
    let esc = escapeHtml(text);
    esc = esc.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    let lines = esc.split('\n');
    let inList = false;
    for (let i = 0; i < lines.length; i++) {
        let l = lines[i].trim();
        if (l.startsWith('- ') || l.startsWith('* ')) {
            if (!inList) { lines[i] = '<ul><li>' + l.substring(2) + '</li>'; inList = true; }
            else { lines[i] = '<li>' + l.substring(2) + '</li>'; }
        } else {
            if (inList) { lines[i-1] += '</ul>'; inList = false; }
        }
    }
    if (inList) lines[lines.length-1] += '</ul>';
    return lines.join('<br>');
}

// =============================================
// PROFILE SETTINGS DIALOG ACTIONS
// =============================================
function openProfileModal() {
    const modal = document.getElementById('profile-modal');
    const nameInput = document.getElementById('profile-new-name');
    const desigText = document.getElementById('modal-profile-designation');
    const roleBadge = document.getElementById('modal-profile-role');
    const errorBox = document.getElementById('profile-error-box');

    errorBox.classList.add('hidden');
    desigText.innerText = state.designation || '';
    
    roleBadge.innerText = state.role.toUpperCase();
    roleBadge.className = `badge badge-${state.role.toLowerCase()}`;

    nameInput.value = state.displayName || '';
    modal.classList.remove('hidden');
    nameInput.focus();
}

function closeProfileModal() {
    document.getElementById('profile-modal').classList.add('hidden');
}

async function handleProfileUpdate(e) {
    e.preventDefault();
    const newName = document.getElementById('profile-new-name').value.trim();
    const errorBox = document.getElementById('profile-error-box');
    const saveBtn = document.getElementById('btn-save-profile');

    errorBox.classList.add('hidden');

    // 1. Length validation
    if (newName.length < 2 || newName.length > 30) {
        showProfileError("Name must be between 2 and 30 characters.");
        return;
    }
    
    // 2. Character validation (letters, spaces, hyphens, apostrophes only)
    const nameRegex = /^[A-Za-z]+([ '-][A-Za-z]+)*$/;
    if (!nameRegex.test(newName)) {
        showProfileError("Name can only contain letters, spaces, hyphens, and apostrophes.");
        return;
    }
    
    // 3. Simple vowel test to reject zxcvb style keyboard random entries
    const vowels = newName.match(/[aeiouAEIOU]/g);
    if (!vowels) {
        showProfileError("Please enter a realistic name containing at least one vowel.");
        return;
    }

    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';

    const formData = new FormData();
    formData.append('username', state.username);
    formData.append('display_name', newName);

    try {
        const res = await fetch(`${API_URL}/update_profile`, { method: 'POST', body: formData });
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                state.displayName = data.display_name;
                sessionStorage.setItem('sop_display_name', data.display_name);
                
                // Update UI elements
                document.getElementById('sidebar-display-name').innerText = data.display_name;
                
                showToast("Profile name updated successfully!", "success");
                closeProfileModal();

                // Reload staff directory if manager
                if (state.role.toLowerCase() === 'manager') {
                    renderStaffDirectory();
                }
            } else {
                showProfileError(data.message || "Failed to update profile name.");
            }
        } else {
            showProfileError("Server error. Please try again later.");
        }
    } catch (err) {
        showProfileError("Cannot reach server. Is the backend running?");
    } finally {
        saveBtn.disabled = false;
        saveBtn.innerHTML = '<i class="fa-solid fa-check"></i> Save & Apply Changes';
    }
}

function showProfileError(msg) {
    const errorBox = document.getElementById('profile-error-box');
    const errorMsg = document.getElementById('profile-error-msg');
    errorMsg.innerText = msg;
    errorBox.classList.remove('hidden');
}
