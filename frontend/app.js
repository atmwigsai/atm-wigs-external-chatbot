// ===== CONFIG =====
// API base URL comes from config.js (window.APP_CONFIG.API_BASE_URL) so the backend domain can
// be changed at deploy time without editing this file. Falls back to localhost in dev, or
// same-origin if neither is set.
const API_BASE_URL =
    (window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) ||
    ((window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
        ? 'http://127.0.0.1:5000'
        : window.location.origin);

// ===== STATE =====
let currentSessionId = null;
let uploadedImageUrl = null;
let sessions = [];

// ===== DOM ELEMENTS =====
const sidebar = document.getElementById('sidebar');
const toggleSidebarBtn = document.getElementById('toggleSidebar');
const newChatBtn = document.getElementById('newChatBtn');
const chatHistory = document.getElementById('chatHistory');
const messagesContainer = document.getElementById('messagesContainer');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const uploadBtn = document.getElementById('uploadBtn');
const fileInput = document.getElementById('fileInput');
const imagePreview = document.getElementById('imagePreview');
const previewImg = document.getElementById('previewImg');
const removeImageBtn = document.getElementById('removeImageBtn');

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', () => {
    loadSessions();       // Chỉ load danh sách sessions có sẵn
    setupEventListeners();
    // Không tự tạo session mới khi load trang
});

// ===== EVENT LISTENERS =====
function setupEventListeners() {
    // Toggle sidebar
    toggleSidebarBtn.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
    });

    // New chat - chỉ tạo khi bấm nút
    newChatBtn.addEventListener('click', createNewSession);

    // Send message
    sendBtn.addEventListener('click', sendMessage);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Auto-resize textarea
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = messageInput.scrollHeight + 'px';
    });

    // Upload image
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileUpload);
    removeImageBtn.addEventListener('click', removeImage);

    // Paste image
    messageInput.addEventListener('paste', handlePaste);
}

// ===== SESSION MANAGEMENT =====
async function loadSessions() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/sessions`);
        const data = await response.json();

        if (data.success) {
            sessions = data.sessions;
            renderSessions();

            // Nếu có session cũ, tự động load session mới nhất
            if (sessions.length > 0) {
                loadSession(sessions[0].id);
            }
            // Nếu không có session nào thì chỉ hiện welcome screen, không tạo mới
        }
    } catch (error) {
        console.error('Error loading sessions:', error);
    }
}

async function createNewSession() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/sessions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: 'New Chat' })
        });

        const data = await response.json();

        if (data.success) {
            currentSessionId = data.session.id;
            sessions.unshift(data.session);
            renderSessions();
            clearMessages();
            messageInput.focus();
        }
    } catch (error) {
        console.error('Error creating session:', error);
        alert('Cannot create new chat session. Please try again.');
    }
}

async function loadSession(sessionId) {
    try {
        currentSessionId = sessionId;

        const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}/messages`);
        const data = await response.json();

        if (data.success) {
            clearMessages();
            data.messages.forEach(msg => {
                addMessage(msg.role, msg.content, msg.image_url, false);
            });

            renderSessions();
        }
    } catch (error) {
        console.error('Error loading session:', error);
    }
}

async function renameSession(sessionId, currentTitle) {
    const newTitle = prompt('Rename session:', currentTitle);

    if (newTitle && newTitle !== currentTitle) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: newTitle })
            });

            const data = await response.json();

            if (data.success) {
                const session = sessions.find(s => s.id === sessionId);
                if (session) {
                    session.title = newTitle;
                    renderSessions();
                }
            }
        } catch (error) {
            console.error('Error renaming session:', error);
        }
    }
}

async function deleteSession(sessionId, title) {
    if (!confirm(`Xoá cuộc trò chuyện "${title}"?\nHành động này không thể hoàn tác.`)) return;
    try {
        const response = await fetch(`${API_BASE_URL}/api/sessions/${sessionId}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.success) {
            sessions = sessions.filter(s => s.id !== sessionId);
            if (currentSessionId === sessionId) {
                currentSessionId = null;
                clearMessages();
            }
            renderSessions();
        } else {
            alert('Không xoá được cuộc trò chuyện. Vui lòng thử lại.');
        }
    } catch (error) {
        console.error('Error deleting session:', error);
        alert('Lỗi kết nối khi xoá cuộc trò chuyện.');
    }
}

function renderSessions() {
    chatHistory.innerHTML = '';

    sessions.forEach(session => {
        const div = document.createElement('div');
        div.className = `chat-item ${session.id === currentSessionId ? 'active' : ''}`;

        div.innerHTML = `
            <i class="fas fa-comment chat-item-icon"></i>
            <span class="chat-item-title">${escapeHtml(session.title)}</span>
            <div class="chat-item-actions">
                <button class="chat-item-action rename-btn" title="Rename">
                    <i class="fas fa-edit"></i>
                </button>
                <button class="chat-item-action delete-btn" title="Delete">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;

        div.addEventListener('click', (e) => {
            if (!e.target.closest('.chat-item-action')) {
                loadSession(session.id);
            }
        });

        div.querySelector('.rename-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            renameSession(session.id, session.title);
        });

        div.querySelector('.delete-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteSession(session.id, session.title);
        });

        chatHistory.appendChild(div);
    });
}

// ===== MESSAGE HANDLING =====
async function sendMessage() {
    const message = messageInput.value.trim();

    if (!message && !uploadedImageUrl) return;

    // Nếu chưa có session, tự động tạo mới khi gửi tin nhắn đầu tiên
    if (!currentSessionId) {
        await createNewSession();
    }

    // Disable input
    messageInput.disabled = true;
    sendBtn.disabled = true;

    // Add user message to UI
    addMessage('user', message, uploadedImageUrl);

    // Clear input
    messageInput.value = '';
    messageInput.style.height = 'auto';
    removeImage();

    // Show typing indicator
    const typingId = showTypingIndicator();

    try {
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sessionId: currentSessionId,
                message: message,
                imageUrl: uploadedImageUrl
            })
        });

        const data = await response.json();

        removeTypingIndicator(typingId);

        if (data.success) {
            addMessage('assistant', data.reply);

            // Đổi tên session theo tin nhắn đầu tiên
            const session = sessions.find(s => s.id === currentSessionId);
            if (session && session.title === 'New Chat') {
                const firstWords = message.split(' ').slice(0, 5).join(' ');
                session.title = firstWords || 'New Chat';

                await fetch(`${API_BASE_URL}/api/sessions/${currentSessionId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title: session.title })
                });

                renderSessions();
            }
        } else {
            addMessage('assistant', 'Sorry, there was an error. Please try again.');
        }
    } catch (error) {
        console.error('Error sending message:', error);
        removeTypingIndicator(typingId);
        addMessage('assistant', 'Cannot connect to server. Please check your connection.');
    } finally {
        messageInput.disabled = false;
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

// Lightweight, dependency-free markdown -> HTML for agent (bot) answers.
// Escape-first => XSS-safe by construction; supports bold/italic/code/headings/lists/tables/links.
function renderBotHtml(md) {
    md = String(md == null ? '' : md).replace(/\r/g, '');
    const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    const inline = (s) => {
        s = esc(s);
        s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
        s = s.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
        s = s.replace(/__([^_]+?)__/g, '<strong>$1</strong>');
        s = s.replace(/(^|[^*])\*([^*\n]+?)\*(?!\*)/g, '$1<em>$2</em>');
        // links: only http/https/mailto (javascript: etc. won't match -> stays escaped text)
        s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+|mailto:[^\s)]+)\)/g,
                      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        return s;
    };
    const isSep = (l) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/.test(l);
    const cells = (l) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
    const lines = md.split('\n');
    let html = '', i = 0, ul = false;
    const closeUl = () => { if (ul) { html += '</ul>'; ul = false; } };
    while (i < lines.length) {
        const line = lines[i];
        if (/\|/.test(line) && i + 1 < lines.length && isSep(lines[i + 1])) {   // table
            closeUl();
            html += '<table><thead><tr>' + cells(line).map((h) => `<th>${inline(h)}</th>`).join('') + '</tr></thead><tbody>';
            i += 2;
            while (i < lines.length && /\|/.test(lines[i]) && lines[i].trim() !== '') {
                html += '<tr>' + cells(lines[i]).map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>';
                i++;
            }
            html += '</tbody></table>';
            continue;
        }
        let m;
        if ((m = line.match(/^\s*(#{1,3})\s+(.*)$/))) {          // heading
            closeUl(); const lvl = m[1].length;
            html += `<h${lvl}>${inline(m[2])}</h${lvl}>`;
        } else if ((m = line.match(/^\s*[-*]\s+(.*)$/))) {        // bullet
            if (!ul) { html += '<ul>'; ul = true; }
            html += `<li>${inline(m[1])}</li>`;
        } else if (line.trim() === '') {                         // blank line
            closeUl();
        } else {                                                 // paragraph
            closeUl(); html += `<p>${inline(line)}</p>`;
        }
        i++;
    }
    closeUl();
    return html;
}

function addMessage(role, content, imageUrl = null, scroll = true) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (imageUrl) {
        const img = document.createElement('img');
        img.src = imageUrl;
        img.className = 'message-image';
        img.alt = 'Uploaded image';
        contentDiv.appendChild(img);
    }

    if (content) {
        const text = document.createElement('div');
        text.className = 'message-text';
        if (role === 'assistant') {
            text.innerHTML = renderBotHtml(content);   // agent markdown (sanitized)
        } else {
            text.textContent = content;                // user input: plain text, no HTML injection
            text.style.whiteSpace = 'pre-wrap';
        }
        contentDiv.appendChild(text);
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);

    const welcomeMsg = messagesContainer.querySelector('.welcome-message');
    if (welcomeMsg) welcomeMsg.remove();

    messagesContainer.appendChild(messageDiv);

    if (scroll) scrollToBottom();
}

function showTypingIndicator() {
    const id = 'typing-' + Date.now();
    const typingDiv = document.createElement('div');
    typingDiv.id = id;
    typingDiv.className = 'message assistant';
    typingDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-content">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;

    messagesContainer.appendChild(typingDiv);
    scrollToBottom();

    return id;
}

function removeTypingIndicator(id) {
    const element = document.getElementById(id);
    if (element) element.remove();
}

function clearMessages() {
    messagesContainer.innerHTML = `
        <div class="welcome-message">
            <h2>Hello!</h2>
            <p>I am ATM WIGS Assistant. How can I help you today?</p>
        </div>
    `;
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// ===== IMAGE HANDLING =====
async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (file) await uploadImage(file);
}

async function handlePaste(e) {
    const items = e.clipboardData.items;

    for (let item of items) {
        if (item.type.indexOf('image') !== -1) {
            e.preventDefault();
            const file = item.getAsFile();
            await uploadImage(file);
            break;
        }
    }
}

async function uploadImage(file) {
    if (!file.type.startsWith('image/')) {
        alert('Please select an image file!');
        return;
    }

    if (file.size > 5 * 1024 * 1024) {
        alert('Image size must not exceed 5MB!');
        return;
    }

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            uploadedImageUrl = data.url;
            previewImg.src = data.url;
            imagePreview.style.display = 'block';
        } else {
            alert('Cannot upload image. Please try again.');
        }
    } catch (error) {
        console.error('Error uploading image:', error);
        alert('Error uploading image!');
    }

    fileInput.value = '';
}

function removeImage() {
    uploadedImageUrl = null;
    imagePreview.style.display = 'none';
    previewImg.src = '';
}

// ===== UTILITIES =====
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
