// State Management
let currentToken = sessionStorage.getItem("rag_token") || null;
let currentUser = JSON.parse(sessionStorage.getItem("rag_user") || "null");
let currentConversationId = null;
let currentView = "chat";
let currentSlideIndex = 0;
let carouselInterval = null;

const sceneNames = [
  "📍 University Main Campus",
  "📍 Central University Library",
  "📍 Smart Lecture Amphitheater",
  "📍 Athletic Stadium & Playground",
  "📍 State-of-the-Art AI Lab"
];

// Initialize Application
document.addEventListener("DOMContentLoaded", async () => {
  // Pre-warm backend in background
  try { fetch("/api/health").catch(() => {}); } catch (e) {}

  if (!currentToken || !currentUser) {
    document.documentElement.classList.remove("logged-in");
    showAuthScreen();
    startCarousel();
    setup3DTilt();
  } else {
    showMainApp();
  }

  setupEventListeners();
});

function setupEventListeners() {
  const chatInput = document.getElementById("chatInput");
  if (chatInput) {
    chatInput.addEventListener("input", () => {
      chatInput.style.height = "auto";
      chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + "px";
    });
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
      }
    });
  }

  const newChatBtn = document.getElementById("newChatBtn");
  if (newChatBtn) {
    newChatBtn.addEventListener("click", () => {
      startNewConversation();
    });
  }
}

// 3D Tilt Physics and Mouse Parallax on Login Card (60FPS Hardware Accelerated)
function setup3DTilt() {
  const card = document.getElementById("auth3DCard");
  const overlay = document.getElementById("authScreen");
  const glare = document.getElementById("cardGlare");
  if (!card || !overlay) return;

  let ticking = false;
  let cachedRect = null;

  const updateCardTransform = (e) => {
    if (!cachedRect) cachedRect = card.getBoundingClientRect();
    const cardCenterX = cachedRect.left + cachedRect.width / 2;
    const cardCenterY = cachedRect.top + cachedRect.height / 2;

    const mouseX = e.clientX - cardCenterX;
    const mouseY = e.clientY - cardCenterY;

    const rotateX = -(mouseY / (window.innerHeight / 2)) * 6;
    const rotateY = (mouseX / (window.innerWidth / 2)) * 6;

    card.style.transform = `perspective(1000px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateZ(4px)`;

    if (glare) {
      const glareX = ((e.clientX - cachedRect.left) / cachedRect.width) * 100;
      const glareY = ((e.clientY - cachedRect.top) / cachedRect.height) * 100;
      glare.style.setProperty("--glare-x", `${glareX}%`);
      glare.style.setProperty("--glare-y", `${glareY}%`);
    }
    ticking = false;
  };

  overlay.addEventListener("mousemove", (e) => {
    if (!ticking) {
      requestAnimationFrame(() => updateCardTransform(e));
      ticking = true;
    }
  }, { passive: true });

  overlay.addEventListener("mouseleave", () => {
    cachedRect = null;
    card.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0px)`;
    card.style.transition = "transform 0.4s ease-out";
  });

  overlay.addEventListener("mouseenter", () => {
    cachedRect = card.getBoundingClientRect();
    card.style.transition = "transform 0.08s ease-out";
  });
}

// Dynamic 5-Scene Background Carousel Controls (Progressive Lazy Loading)
function startCarousel() {
  if (carouselInterval) clearInterval(carouselInterval);
  const slides = document.querySelectorAll(".carousel-bg-slide");
  if (!slides || slides.length === 0) return;

  // Defer preloading slides 1-4 until after main page interaction is ready
  setTimeout(() => {
    slides.forEach((s) => {
      if (s.dataset.bg && !s.style.backgroundImage) {
        const img = new Image();
        img.src = s.dataset.bg;
        img.onload = () => {
          s.style.backgroundImage = `url('${s.dataset.bg}')`;
        };
      }
    });
  }, 1000);

  carouselInterval = setInterval(() => {
    setCarouselSlide((currentSlideIndex + 1) % slides.length);
  }, 5500);
}

function setCarouselSlide(index) {
  const slides = document.querySelectorAll(".carousel-bg-slide");
  if (!slides || slides.length === 0) return;

  currentSlideIndex = index;
  slides.forEach((s, idx) => {
    if (idx === index) {
      if (s.dataset.bg && !s.style.backgroundImage) {
        s.style.backgroundImage = `url('${s.dataset.bg}')`;
      }
      s.classList.add("active");
    } else {
      s.classList.remove("active");
    }
  });
}

function quickFillCredentials(email, password) {
  document.getElementById("loginEmail").value = email;
  document.getElementById("loginPassword").value = password;
  document.getElementById("authErrorMessage").style.display = "none";
}

// Auth UI Controls
function showAuthScreen() {
  document.documentElement.classList.remove("logged-in");
  const authEl = document.getElementById("authScreen");
  const mainEl = document.getElementById("mainAppLayout");
  if (authEl) authEl.style.display = "flex";
  if (mainEl) mainEl.style.display = "none";

  // Reset form inputs to blank
  const emailInput = document.getElementById("loginEmail");
  const passInput = document.getElementById("loginPassword");
  if (emailInput) emailInput.value = "";
  if (passInput) passInput.value = "";

  const regName = document.getElementById("regName");
  const regEmail = document.getElementById("regEmail");
  const regDept = document.getElementById("regDept");
  const regPassword = document.getElementById("regPassword");
  if (regName) regName.value = "";
  if (regEmail) regEmail.value = "";
  if (regDept) regDept.value = "";
  if (regPassword) regPassword.value = "";

  const authErr = document.getElementById("authErrorMessage");
  if (authErr) authErr.style.display = "none";
  const regErr = document.getElementById("regErrorMessage");
  if (regErr) regErr.style.display = "none";

  switchAuthTab("login");
  startCarousel();
}

async function showMainApp() {
  document.documentElement.classList.add("logged-in");
  if (carouselInterval) clearInterval(carouselInterval);
  const authEl = document.getElementById("authScreen");
  const mainEl = document.getElementById("mainAppLayout");
  if (authEl) authEl.style.display = "none";
  if (mainEl) mainEl.style.display = "flex";
  updateUserUI();

  // Reset view to chat
  currentView = "chat";
  const tabChat = document.getElementById("tabChat");
  const tabAdmin = document.getElementById("tabAdmin");
  if (tabChat) tabChat.classList.add("active");
  if (tabAdmin) tabAdmin.classList.remove("active");
  document.getElementById("chatView").style.display = "flex";
  document.getElementById("adminView").style.display = "none";

  const savedConvId = sessionStorage.getItem("rag_active_conv");

  if (savedConvId) {
    // Only restore active conversation if the user was actively chatting before page refresh
    currentConversationId = savedConvId;
    const cached = sessionStorage.getItem(`rag_msgs_${savedConvId}`);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (parsed && parsed.length > 0) {
          renderMessages(parsed);
        }
      } catch (e) {}
    }

    await Promise.all([
      loadConversations(),
      fetchActiveConversation(savedConvId)
    ]);
  } else {
    // Fresh login: start on clean Welcome Screen with prompt suggestions
    currentConversationId = null;
    const msgContainer = document.getElementById("messagesContainer");
    if (msgContainer) msgContainer.innerHTML = getWelcomeScreenHTML();

    // Load past conversations in sidebar without auto-opening old messages
    await loadConversations();
  }
}

async function fetchActiveConversation(convId) {
  currentConversationId = convId;
  document.querySelectorAll(".conversation-item").forEach(item => {
    item.classList.toggle("active", item.dataset.id === convId);
  });
  try {
    const res = await fetch(`/api/chat/conversations/${convId}`, {
      headers: { Authorization: `Bearer ${currentToken}` },
    });
    if (res.ok) {
      const data = await res.json();
      const msgs = data.messages || [];
      renderMessages(msgs);
      try {
        sessionStorage.setItem(`rag_msgs_${convId}`, JSON.stringify(msgs));
      } catch (e) {}
    }
  } catch (e) {}
}

function switchAuthTab(tab) {
  const isLogin = tab === "login";
  document.getElementById("authTabLogin").classList.toggle("active", isLogin);
  document.getElementById("authTabRegister").classList.toggle("active", !isLogin);
  document.getElementById("loginForm").style.display = isLogin ? "block" : "none";
  document.getElementById("registerForm").style.display = isLogin ? "none" : "block";
  
  document.getElementById("authErrorMessage").style.display = "none";
  document.getElementById("regErrorMessage").style.display = "none";
}

function toggleSidebar() {
  const sidebar = document.getElementById("appSidebar");
  const expandBtn = document.getElementById("expandSidebarBtn");
  if (!sidebar) return;

  const isCollapsed = sidebar.classList.toggle("collapsed");
  if (expandBtn) {
    expandBtn.style.display = isCollapsed ? "inline-flex" : "none";
  }
}

function updateUserUI() {
  if (currentUser) {
    document.getElementById("userName").innerText = currentUser.name || "Student";
    const role = (currentUser.role || "USER").toUpperCase();
    document.getElementById("userRole").innerText = role;
    document.getElementById("userAvatar").innerText = (currentUser.name || "U")[0].toUpperCase();

    const isAdmin = currentUser.role === "admin" || currentUser.role === "super-admin";
    const sidebarNavTabs = document.getElementById("sidebarNavTabs");
    const tabAdmin = document.getElementById("tabAdmin");
    const topAdminBtn = document.getElementById("topAdminBtn");
    
    // Only show dual navigation tabs if the user is an admin
    if (sidebarNavTabs) sidebarNavTabs.style.display = isAdmin ? "flex" : "none";
    if (tabAdmin) tabAdmin.style.display = isAdmin ? "block" : "none";
    if (topAdminBtn) {
      topAdminBtn.style.display = isAdmin ? "inline-block" : "none";
      topAdminBtn.innerText = "⚙️ Admin Portal";
      topAdminBtn.onclick = () => switchView("admin");
    }
  }
}

async function handleAuthSubmit(event, mode) {
  event.preventDefault();
  
  if (mode === "login") {
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value.trim();
    const errorEl = document.getElementById("authErrorMessage");
    errorEl.style.display = "none";
    
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        currentToken = data.access_token;
        currentUser = { id: data.user_id, name: data.name, email: data.email, role: data.role };
        sessionStorage.setItem("rag_token", currentToken);
        sessionStorage.setItem("rag_user", JSON.stringify(currentUser));
        localStorage.removeItem("rag_token");
        localStorage.removeItem("rag_user");
        showMainApp();
      } else {
        const msg = data.detail?.message || data.detail || "Authentication failed. Check credentials.";
        errorEl.innerText = msg;
        errorEl.style.display = "block";
      }
    } catch (err) {
      errorEl.innerText = "Cannot reach server. Make sure `python scripts/run_dev.py` is running.";
      errorEl.style.display = "block";
    }
  } else if (mode === "register") {
    const name = document.getElementById("regName").value.trim();
    const email = document.getElementById("regEmail").value.trim();
    const department_id = document.getElementById("regDept").value.trim() || null;
    const password = document.getElementById("regPassword").value.trim();
    const errorEl = document.getElementById("regErrorMessage");
    errorEl.style.display = "none";

    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, department_id, password, role: "user" }),
      });
      
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        currentToken = data.access_token;
        currentUser = { id: data.user_id, name: data.name, email: data.email, role: data.role };
        sessionStorage.setItem("rag_token", currentToken);
        sessionStorage.setItem("rag_user", JSON.stringify(currentUser));
        localStorage.removeItem("rag_token");
        localStorage.removeItem("rag_user");
        showMainApp();
      } else {
        const msg = data.detail?.message || data.detail || "Registration failed.";
        errorEl.innerText = msg;
        errorEl.style.display = "block";
      }
    } catch (err) {
      errorEl.innerText = "Cannot reach server. Make sure `python scripts/run_dev.py` is running.";
      errorEl.style.display = "block";
    }
  }
}

function handleLogout() {
  currentToken = null;
  currentUser = null;
  currentConversationId = null;
  try {
    localStorage.clear();
    sessionStorage.clear();
  } catch (e) {}

  document.documentElement.classList.remove("logged-in");

  // Clear messages, conversation lists, and inputs from memory & DOM
  const msgContainer = document.getElementById("messagesContainer");
  if (msgContainer) msgContainer.innerHTML = "";
  const listEl = document.getElementById("conversationsList");
  if (listEl) listEl.innerHTML = "";
  const chatInput = document.getElementById("chatInput");
  if (chatInput) chatInput.value = "";

  showAuthScreen();
}

function switchView(view) {
  const isAdmin = currentUser && (currentUser.role === "admin" || currentUser.role === "super-admin");
  if (view === "admin" && !isAdmin) {
    alert("Access Denied: Admin portal is restricted to administrators only. Please sign in with an administrator account.");
    return;
  }

  currentView = view;
  const tabChat = document.getElementById("tabChat");
  const tabAdmin = document.getElementById("tabAdmin");
  const topAdminBtn = document.getElementById("topAdminBtn");
  const viewHeaderTitle = document.getElementById("viewHeaderTitle");

  if (tabChat) tabChat.classList.toggle("active", view === "chat");
  if (tabAdmin) tabAdmin.classList.toggle("active", view === "admin");
  
  document.getElementById("chatView").style.display = view === "chat" ? "flex" : "none";
  document.getElementById("adminView").style.display = view === "admin" ? "flex" : "none";

  if (view === "admin") {
    if (viewHeaderTitle) viewHeaderTitle.innerText = "Knowledge Base & Analytics Dashboard";
    if (topAdminBtn) {
      topAdminBtn.innerText = "💬 Open Chatbot";
      topAdminBtn.onclick = () => switchView("chat");
    }
    loadAdminDashboard();
  } else {
    if (viewHeaderTitle) viewHeaderTitle.innerText = "College Information Desk";
    if (topAdminBtn) {
      topAdminBtn.innerText = "⚙️ Admin Portal";
      topAdminBtn.onclick = () => switchView("admin");
    }
  }
}

// Conversation Management
let allConversations = [];

async function loadConversations() {
  if (!currentToken) return [];
  try {
    const res = await fetch("/api/chat/conversations", {
      headers: { Authorization: `Bearer ${currentToken}` },
    });
    if (res.ok) {
      allConversations = await res.json();
      renderConversationsList(allConversations);
      return allConversations;
    } else if (res.status === 401) {
      handleLogout();
      return [];
    }
  } catch (err) {
    console.error("Failed to load conversations:", err);
  }
  return [];
}

function renderConversationsList(convs) {
  const listEl = document.getElementById("conversationsList");
  if (!listEl) return;
  listEl.innerHTML = "";

  if (!convs || convs.length === 0) {
    listEl.innerHTML = `<div style="font-size:0.75rem; color:var(--text-muted); text-align:center; padding:16px 0;">No conversations found</div>`;
    return;
  }

  convs.forEach((c) => {
    const item = document.createElement("div");
    item.className = `conversation-item ${c.id === currentConversationId ? "active" : ""}`;
    item.dataset.id = c.id;
    item.onclick = () => selectConversation(c.id);
    item.innerHTML = `
      <div class="conversation-title">${c.title || "New Chat"}</div>
      <button class="action-icon-btn" onclick="event.stopPropagation(); deleteConversation('${c.id}')" title="Delete conversation">✕</button>
    `;
    listEl.appendChild(item);
  });
}

function handleSearchConversations(query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) {
    renderConversationsList(allConversations);
    return;
  }
  const filtered = allConversations.filter(c => (c.title || "New Chat").toLowerCase().includes(q));
  renderConversationsList(filtered);
}

function getWelcomeScreenHTML() {
  const firstName = (currentUser && currentUser.name) ? currentUser.name.split(" ")[0] : "Student";
  return `
    <div class="welcome-screen-box">
      <div class="welcome-hero-header">
        <div class="welcome-logo-glow">
          <img src="/static/images/logo.png?v=14.0" alt="Logo" class="welcome-logo-img">
        </div>
        <div class="rag-status-hero-pill">
          <span class="status-dot"></span>
          <span>Verified Campus RAG • 5 Official Handbooks Indexed</span>
        </div>
        <h2 class="welcome-hero-title">Welcome back, ${firstName}! 👋</h2>
        <p class="welcome-hero-desc">Ask any verified question regarding college admissions, fee schedules, hostel curfews, exam regulations, or academic calendars.</p>
      </div>

      <div class="capability-cards-grid">
        <div class="capability-card" onclick="askPreset('What is the last date to apply for admission and what are the eligibility criteria?')">
          <div class="cap-card-top">
            <div class="cap-icon-tag-group">
              <span class="cap-icon">🎓</span>
              <span class="cap-tag">Admissions</span>
            </div>
            <span class="cap-arrow">→</span>
          </div>
          <div class="cap-title">Admissions & Eligibility</div>
          <div class="cap-desc">Cutoff scores, document verification, application deadlines & entry requirements.</div>
        </div>

        <div class="capability-card" onclick="askPreset('What is the annual fee structure for CSE first year and installment deadlines?')">
          <div class="cap-card-top">
            <div class="cap-icon-tag-group">
              <span class="cap-icon">💰</span>
              <span class="cap-tag">Tuition & Aid</span>
            </div>
            <span class="cap-arrow">→</span>
          </div>
          <div class="cap-title">Fees & Scholarships</div>
          <div class="cap-desc">Branch fee breakdowns, installment schedules, and merit-based financial aid.</div>
        </div>

        <div class="capability-card" onclick="askPreset('What are the hostel room rent, mess charges, and evening curfew timings?')">
          <div class="cap-card-top">
            <div class="cap-icon-tag-group">
              <span class="cap-icon">🏢</span>
              <span class="cap-tag">Hostel Life</span>
            </div>
            <span class="cap-arrow">→</span>
          </div>
          <div class="cap-title">Hostel & Curfews</div>
          <div class="cap-desc">Room allocations, mess meal timings, amenities, and security regulations.</div>
        </div>

        <div class="capability-card" onclick="askPreset('What is the minimum attendance required for semester exams and grading policies?')">
          <div class="cap-card-top">
            <div class="cap-icon-tag-group">
              <span class="cap-icon">📅</span>
              <span class="cap-tag">Academics</span>
            </div>
            <span class="cap-arrow">→</span>
          </div>
          <div class="cap-title">Exams & Attendance</div>
          <div class="cap-desc">75% attendance rule, grade calculations, academic calendar & re-exam policies.</div>
        </div>
      </div>
    </div>
  `;
}

async function startNewConversation() {
  if (!currentToken) return;
  // Instant UI reset
  currentConversationId = null;
  try {
    sessionStorage.removeItem("rag_active_conv");
  } catch (e) {}
  document.getElementById("messagesContainer").innerHTML = getWelcomeScreenHTML();
  document.querySelectorAll(".conversation-item").forEach(item => item.classList.remove("active"));
  
  try {
    const res = await fetch("/api/chat/conversations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${currentToken}`,
      },
      body: JSON.stringify({ title: "New Conversation", language: "en" }),
    });
    if (res.ok) {
      const data = await res.json();
      currentConversationId = data.id;
      try {
        sessionStorage.setItem("rag_active_conv", data.id);
      } catch (e) {}
      allConversations.unshift({ id: data.id, title: data.title || "New Conversation" });
      renderConversationsList(allConversations);
    }
  } catch (err) {
    console.error("Error creating conversation:", err);
  }
}

async function selectConversation(convId) {
  if (currentConversationId === convId && document.getElementById("messagesContainer").children.length > 0) {
    return;
  }
  currentConversationId = convId;
  try {
    sessionStorage.setItem("rag_active_conv", convId);
  } catch (e) {}
  
  // Instant local active class highlight without re-fetching all conversations
  document.querySelectorAll(".conversation-item").forEach(item => {
    item.classList.toggle("active", item.dataset.id === convId);
  });

  // Instant render from local cache if available (0ms)
  const cached = sessionStorage.getItem(`rag_msgs_${convId}`);
  if (cached) {
    try {
      const parsed = JSON.parse(cached);
      if (parsed && parsed.length > 0) {
        renderMessages(parsed);
      }
    } catch (e) {}
  }

  try {
    const res = await fetch(`/api/chat/conversations/${convId}`, {
      headers: { Authorization: `Bearer ${currentToken}` },
    });
    if (res.ok) {
      const data = await res.json();
      const msgs = data.messages || [];
      renderMessages(msgs);
      try {
        sessionStorage.setItem(`rag_msgs_${convId}`, JSON.stringify(msgs));
      } catch (e) {}
    }
  } catch (err) {
    console.error("Failed to load conversation messages:", err);
  }
}

async function deleteConversation(convId) {
  // Instant optimistic removal from UI (0ms)
  const prevConvs = [...allConversations];
  allConversations = allConversations.filter(c => c.id !== convId);
  renderConversationsList(allConversations);

  if (currentConversationId === convId) {
    if (allConversations.length > 0) {
      selectConversation(allConversations[0].id);
    } else {
      currentConversationId = null;
      document.getElementById("messagesContainer").innerHTML = getWelcomeScreenHTML();
    }
  }

  try {
    const res = await fetch(`/api/chat/conversations/${convId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${currentToken}` },
    });
    if (!res.ok) {
      allConversations = prevConvs;
      renderConversationsList(allConversations);
    }
  } catch (err) {
    console.error("Delete conversation error:", err);
    allConversations = prevConvs;
    renderConversationsList(allConversations);
  }
}

// Chat & RAG Messaging
function renderMessages(messages) {
  const container = document.getElementById("messagesContainer");
  container.innerHTML = "";

  if (!messages || messages.length === 0) {
    container.innerHTML = getWelcomeScreenHTML();
    return;
  }

  messages.forEach((msg) => {
    appendMessageToDOM(msg.role, msg.content, msg.sources, msg.evidence_status, msg.id, msg.usage);
  });
  container.scrollTop = container.scrollHeight;
}

function appendMessageToDOM(role, content, sources = [], evidenceStatus = "grounded", messageId = null, usage = null) {
  const container = document.getElementById("messagesContainer");
  
  // Clear the welcome placeholder if present before adding first chat bubble
  if (container.querySelector(".welcome-screen-box")) {
    container.innerHTML = "";
  }

  const msgWrapper = document.createElement("div");
  msgWrapper.className = `message-wrapper ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  if (role === "user") {
    avatar.innerText = "👤";
  } else {
    avatar.innerHTML = `<img src="/static/images/logo.png?v=14.0" alt="Bot" style="width: 100%; height: 100%; border-radius: 8px; object-fit: cover;">`;
  }

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  if (role === "assistant") {
    let statusClass = evidenceStatus === "grounded" ? "grounded" : "insufficient_evidence";
    let statusText = evidenceStatus === "grounded" ? "Verified Grounded Answer" : "Insufficient Knowledge Base Context";
    const msgUid = messageId || "msg-" + Math.random().toString(36).substring(2, 9);
    
    let html = `<div class="evidence-badge ${statusClass}">● ${statusText}</div>`;
    html += `<div class="message-text">${formatMarkdown(content)}</div>`;

    if (sources && sources.length > 0) {
      html += `
        <div class="sources-toggle-wrapper">
          <button type="button" class="sources-pill-btn" onclick="toggleSourcesDrawer(this, '${msgUid}')" title="Click to view supporting official handbooks">
            <span class="sources-pill-icon">📚</span>
            <span class="sources-pill-count">${sources.length} ${sources.length === 1 ? 'Source' : 'Sources'}</span>
            <svg class="sources-pill-chevron" viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
              <path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
        
        <div id="sources-container-${msgUid}" class="sources-card-container collapsed">
          <div class="sources-header">
            <div class="sources-header-left">
              <span>📚 Supporting Official Handbooks (${sources.length})</span>
            </div>
            <button type="button" class="sources-close-btn" onclick="closeSourcesDrawer('${msgUid}')" title="Hide Sources">✕ Close</button>
          </div>
          <div class="sources-list">
      `;
      sources.forEach((s, idx) => {
        let citeNum = s.citation ? s.citation.replace(/[\[\]]/g, '') : (idx + 1);
        let loc = s.page ? `Page ${s.page}` : "";
        if (s.section) loc += loc ? ` • ${s.section}` : s.section;
        html += `
          <div class="source-item" id="source-item-${msgUid}-${citeNum}">
            <div class="source-title">
              <div class="source-title-left">
                <span class="source-num-tag">[${citeNum}]</span>
                <span class="source-name">${s.title || "Official College Document"}</span>
                <span class="source-ver-tag">${s.version || "Latest"}</span>
              </div>
              ${loc ? `<span class="source-loc-tag">${loc}</span>` : ''}
            </div>
            <div class="source-snippet">"${s.snippet || ""}"</div>
          </div>
        `;
      });
      html += `
          </div>
        </div>
      `;
    }

    const rawSafeText = encodeURIComponent(content);
    html += `
      <div class="msg-footer-bar">
        <span>${usage ? `⚡ ${usage.retrieval_ms}ms search • ${usage.generation_ms}ms model` : 'Verified RAG Retrieval'}</span>
        <div class="msg-action-btns">
          <button class="msg-action-btn" onclick="copyMessageContent(this, decodeURIComponent('${rawSafeText}'))" title="Copy response">
            <span>📋 Copy</span>
          </button>
          ${messageId ? `
            <button class="msg-action-btn" onclick="submitFeedback('${messageId}', 'helpful')" title="Helpful">👍</button>
            <button class="msg-action-btn" onclick="submitFeedback('${messageId}', 'not_helpful')" title="Not Helpful">👎</button>
          ` : ''}
        </div>
      </div>
    `;

    bubble.innerHTML = html;
  } else {
    bubble.innerText = content;
  }

  msgWrapper.appendChild(avatar);
  msgWrapper.appendChild(bubble);
  container.appendChild(msgWrapper);
  container.scrollTop = container.scrollHeight;
}

function cleanMessageContent(text) {
  if (!text) return "";
  let cleaned = text;
  // Remove trailing **Sources**: ... and **Evidence status**: ... if embedded in raw LLM text
  cleaned = cleaned.replace(/\n*\*\*Sources\*\*:\s*[\s\S]*?(?=\n\*\*(?:Evidence status|Conditions)|\s*$)/gi, "");
  cleaned = cleaned.replace(/\n*\*\*Evidence status\*\*:\s*[\s\S]*$/gi, "");
  cleaned = cleaned.replace(/^\*\*Answer\*\*:\s*\n?/i, "");
  return cleaned.trim();
}

function formatMarkdown(text) {
  if (!text) return "";
  let cleaned = cleanMessageContent(text);
  
  // Format code blocks
  cleaned = cleaned.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  // Format inline code
  cleaned = cleaned.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Format bold
  cleaned = cleaned.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  // Format italics
  cleaned = cleaned.replace(/\*(.*?)\*/g, "<em>$1</em>");
  // Format interactive citation badges like [1], [2] (ChatGPT / Gemini style)
  cleaned = cleaned.replace(/\[(\d+)\]/g, (match, p1) => {
    return `<button type="button" class="inline-cite-badge" onclick="handleInlineCitationClick(this, '${p1}')" title="View Source [${p1}]">${p1}</button>`;
  });
  // Convert newlines to breaks
  cleaned = cleaned.replace(/\n/g, "<br>");
  return cleaned;
}

function toggleSourcesDrawer(btn, msgUid) {
  const container = document.getElementById(`sources-container-${msgUid}`);
  if (!container) return;
  const isCollapsed = container.classList.contains("collapsed");
  if (isCollapsed) {
    container.classList.remove("collapsed");
    container.classList.add("expanded");
    btn.classList.add("active");
  } else {
    container.classList.add("collapsed");
    container.classList.remove("expanded");
    btn.classList.remove("active");
  }
}

function closeSourcesDrawer(msgUid) {
  const container = document.getElementById(`sources-container-${msgUid}`);
  if (!container) return;
  container.classList.add("collapsed");
  container.classList.remove("expanded");
  const wrapper = container.previousElementSibling;
  if (wrapper) {
    const btn = wrapper.querySelector(".sources-pill-btn");
    if (btn) btn.classList.remove("active");
  }
}

function handleInlineCitationClick(btn, citeNum) {
  const bubble = btn.closest(".message-bubble");
  if (!bubble) return;
  const container = bubble.querySelector(".sources-card-container");
  const toggleBtn = bubble.querySelector(".sources-pill-btn");
  if (container) {
    container.classList.remove("collapsed");
    container.classList.add("expanded");
    if (toggleBtn) toggleBtn.classList.add("active");
    
    // Smooth scroll and pulse-highlight the specific source card
    const targetItem = container.querySelector(`[id$="-${citeNum}"]`);
    if (targetItem) {
      targetItem.scrollIntoView({ behavior: "smooth", block: "nearest" });
      targetItem.classList.add("source-highlight-flash");
      setTimeout(() => {
        targetItem.classList.remove("source-highlight-flash");
      }, 2000);
    }
  }
}

function copyMessageContent(btn, text) {
  navigator.clipboard.writeText(text).then(() => {
    const original = btn.innerHTML;
    btn.innerHTML = `<span>✓ Copied!</span>`;
    btn.style.color = "var(--success)";
    btn.style.borderColor = "var(--success)";
    setTimeout(() => {
      btn.innerHTML = original;
      btn.style.color = "";
      btn.style.borderColor = "";
    }, 2000);
  }).catch(() => {
    alert("Response copied to clipboard!");
  });
}

async function handleSendMessage() {
  const inputEl = document.getElementById("chatInput");
  const question = inputEl.value.trim();
  if (!question || !currentToken) return;

  inputEl.value = "";
  inputEl.style.height = "auto";

  // If no conversation currently selected, create one on the fly
  if (!currentConversationId) {
    try {
      const res = await fetch("/api/chat/conversations", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${currentToken}`,
        },
        body: JSON.stringify({ title: question.slice(0, 30), language: "en" }),
      });
      if (res.ok) {
        const data = await res.json();
        currentConversationId = data.id;
        allConversations.unshift({ id: data.id, title: data.title || question.slice(0, 35) });
        renderConversationsList(allConversations);
      } else {
        return;
      }
    } catch (e) {
      return;
    }
  }

  appendMessageToDOM("user", question);

  const container = document.getElementById("messagesContainer");
  const tempMsg = document.createElement("div");
  tempMsg.id = "tempThinkingMsg";
  tempMsg.className = "message-wrapper assistant";
  tempMsg.innerHTML = `
    <div class="msg-avatar"><img src="/static/images/logo.png?v=14.0" alt="Bot" style="width: 100%; height: 100%; border-radius: 8px; object-fit: cover;"></div>
    <div class="message-bubble">
      <div class="thinking-bubble">
        <div class="thinking-dots">
          <span class="thinking-dot"></span>
          <span class="thinking-dot"></span>
          <span class="thinking-dot"></span>
        </div>
        <span>Searching official handbooks & generating verified answer...</span>
      </div>
    </div>
  `;
  container.appendChild(tempMsg);
  container.scrollTop = container.scrollHeight;

  try {
    const res = await fetch(`/api/chat/conversations/${currentConversationId}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${currentToken}`,
      },
      body: JSON.stringify({ question, language: "en" }),
    });

    const tempEl = document.getElementById("tempThinkingMsg");
    if (tempEl) tempEl.remove();

    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      appendMessageToDOM("assistant", data.answer, data.sources, data.evidence_status, data.message_id, data.usage);
      const activeConv = allConversations.find(c => c.id === currentConversationId);
      if (activeConv && (activeConv.title === "New Conversation" || activeConv.title === "New Chat")) {
        activeConv.title = question.slice(0, 35) + (question.length > 35 ? "..." : "");
        renderConversationsList(allConversations);
      }
    } else {
      const errDetail = data.detail?.message || data.detail || "Error connecting to the college knowledge base.";
      appendMessageToDOM("assistant", `⚠️ ${errDetail}`);
    }
  } catch (err) {
    const tempEl = document.getElementById("tempThinkingMsg");
    if (tempEl) tempEl.remove();
    appendMessageToDOM("assistant", "⚠️ Cannot connect to backend server. Make sure `python scripts/run_dev.py` is running.");
  }
}

function askPreset(presetText) {
  const chatInput = document.getElementById("chatInput");
  if (chatInput) {
    chatInput.value = presetText;
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + "px";
    handleSendMessage();
  }
}

async function submitFeedback(messageId, rating) {
  if (!messageId) return;
  try {
    await fetch(`/api/chat/messages/${messageId}/feedback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${currentToken}`,
      },
      body: JSON.stringify({ rating, reason: "" }),
    });
    alert("Thank you for your feedback!");
  } catch (err) {
    console.error("Feedback error:", err);
  }
}

// Admin Dashboard Functions
async function loadAdminDashboard() {
  try {
    const [overviewRes, docsRes, auditRes] = await Promise.all([
      fetch("/api/admin/analytics/overview", { headers: { Authorization: `Bearer ${currentToken}` } }),
      fetch("/api/admin/documents", { headers: { Authorization: `Bearer ${currentToken}` } }),
      fetch("/api/admin/audit-logs", { headers: { Authorization: `Bearer ${currentToken}` } }),
    ]);

    if (overviewRes.ok) {
      const overview = await overviewRes.json();
      document.getElementById("metricPublishedDocs").innerText = overview.published_documents;
      document.getElementById("metricTotalChunks").innerText = overview.total_chunks;
      document.getElementById("metricTotalQueries").innerText = overview.total_queries;
      document.getElementById("metricUnansweredRate").innerText = `${overview.unanswered_rate_percent}%`;
    }

    if (docsRes.ok) {
      const docs = await docsRes.json();
      const tbody = document.getElementById("documentsTableBody");
      tbody.innerHTML = "";
      docs.forEach((d) => {
        const row = document.createElement("tr");
        const statusBadge = d.status === "published" 
          ? `<span style="color: var(--success); font-weight: 600;">● Published</span>`
          : `<span style="color: var(--warning); font-weight: 600;">○ ${d.status}</span>`;
        row.innerHTML = `
          <td><strong>${d.title}</strong></td>
          <td><span class="collection-badge">${d.collection_name}</span></td>
          <td>${d.version}</td>
          <td>${statusBadge}</td>
          <td>${d.chunk_count}</td>
          <td>
            <button class="btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;" onclick="publishDocument('${d.id}')">Publish</button>
            <button class="btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;" onclick="archiveDocument('${d.id}')">Archive</button>
            <button class="btn-secondary" style="padding: 4px 8px; font-size: 0.75rem;" onclick="reindexDocument('${d.id}')">Reindex</button>
          </td>
        `;
        tbody.appendChild(row);
      });
    }

    if (auditRes.ok) {
      const logs = await auditRes.json();
      const tbody = document.getElementById("auditTableBody");
      tbody.innerHTML = "";
      logs.slice(0, 10).forEach((l) => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${new Date(l.created_at).toLocaleString()}</td>
          <td><code>${l.action}</code></td>
          <td>${l.entity_type}</td>
          <td>${l.actor_user_id.slice(0, 8)}...</td>
        `;
        tbody.appendChild(row);
      });
    }
  } catch (err) {
    console.error("Admin dashboard load error:", err);
  }
}

async function publishDocument(docId) {
  await fetch(`/api/admin/documents/${docId}/publish`, {
    method: "POST",
    headers: { Authorization: `Bearer ${currentToken}` },
  });
  loadAdminDashboard();
}

async function archiveDocument(docId) {
  await fetch(`/api/admin/documents/${docId}/archive`, {
    method: "POST",
    headers: { Authorization: `Bearer ${currentToken}` },
  });
  loadAdminDashboard();
}

async function reindexDocument(docId) {
  await fetch(`/api/admin/documents/${docId}/reindex`, {
    method: "POST",
    headers: { Authorization: `Bearer ${currentToken}` },
  });
  alert("Reindexing job queued!");
  loadAdminDashboard();
}

function openUploadModal() {
  document.getElementById("uploadModal").style.display = "flex";
}
function closeUploadModal() {
  document.getElementById("uploadModal").style.display = "none";
}

function openUserSettingsModal() {
  const modal = document.getElementById("userSettingsModal");
  if (!modal) return;

  if (currentUser) {
    const avatarLetter = (currentUser.name || "U")[0].toUpperCase();
    const avatarEl = document.getElementById("modalUserAvatar");
    const nameEl = document.getElementById("modalUserName");
    const emailEl = document.getElementById("modalUserEmail");
    const badgeEl = document.getElementById("modalUserRoleBadge");

    if (avatarEl) avatarEl.innerText = avatarLetter;
    if (nameEl) nameEl.innerText = currentUser.name || "Student";
    if (emailEl) emailEl.innerText = currentUser.email || "student@college.edu";
    
    const isAdmin = currentUser.role === "admin" || currentUser.role === "super-admin";
    if (badgeEl) {
      badgeEl.innerText = isAdmin ? "⚙️ Campus Administrator" : "🎓 Verified Scholar";
    }
  }

  // Restore saved language preference
  const savedLang = localStorage.getItem("rag_pref_language");
  if (savedLang) {
    const selectEl = document.getElementById("settingLanguage");
    if (selectEl) selectEl.value = savedLang;
  }

  modal.style.display = "flex";
}

function closeUserSettingsModal() {
  const modal = document.getElementById("userSettingsModal");
  if (modal) modal.style.display = "none";
}

function updateUserPreference(key, value) {
  localStorage.setItem(`rag_pref_${key}`, value);
}

async function handleUpload(e) {
  e.preventDefault();
  const title = document.getElementById("uploadTitle").value.trim();
  const collection_id = document.getElementById("uploadCollection").value;
  const fileInput = document.getElementById("uploadFile");
  if (!fileInput.files.length) return;

  const formData = new FormData();
  formData.append("title", title);
  formData.append("collection_id", collection_id);
  formData.append("file", fileInput.files[0]);
  formData.append("version", "v1.0");

  try {
    const res = await fetch("/api/admin/documents", {
      method: "POST",
      headers: { Authorization: `Bearer ${currentToken}` },
      body: formData,
    });
    if (res.ok) {
      alert("Document uploaded and ingestion started!");
      closeUploadModal();
      loadAdminDashboard();
    } else {
      const err = await res.json();
      alert(`Upload failed: ${err.detail?.message || err.detail || "Error"}`);
    }
  } catch (err) {
    alert("Network error uploading document.");
  }
}

// ==============================================================================
// HIGH-ACCURACY VOICE INPUT (SPEECH-TO-TEXT) & AUTOMATIC SEND
// ==============================================================================
let voiceRecognition = null;
let isVoiceListening = false;
let voiceSilenceTimer = null;
let finalTranscribedText = "";

function initVoiceRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    return null;
  }

  const recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 3;
  // Adaptive language selection for optimal college query transcription
  recognition.lang = (navigator.language && navigator.language.startsWith("en")) ? navigator.language : "en-IN";

  recognition.onstart = () => {
    isVoiceListening = true;
    finalTranscribedText = "";
    if (voiceSilenceTimer) clearTimeout(voiceSilenceTimer);

    const voiceBtn = document.getElementById("voiceBtn");
    const chatInput = document.getElementById("chatInput");
    if (voiceBtn) {
      voiceBtn.classList.add("listening");
      voiceBtn.title = "🎙️ Listening... Speak now (Auto-sends on pause or click to send)";
    }
    if (chatInput) {
      chatInput.placeholder = "🎙️ Listening to your voice... (Auto-sends when you pause speaking)";
    }
  };

  recognition.onresult = (event) => {
    let interimTranscript = "";
    let finalChunk = "";

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const res = event.results[i];
      let bestTranscript = res[0].transcript;
      if (res.isFinal) {
        finalChunk += bestTranscript + " ";
      } else {
        interimTranscript += bestTranscript;
      }
    }

    if (finalChunk) {
      finalTranscribedText += finalChunk;
    }

    const currentText = (finalTranscribedText + interimTranscript).trim();
    const chatInput = document.getElementById("chatInput");
    if (chatInput && currentText) {
      chatInput.value = currentText;
      chatInput.style.height = "auto";
      chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + "px";

      // Reset auto-send timer on every spoken syllable
      if (voiceSilenceTimer) clearTimeout(voiceSilenceTimer);
      voiceSilenceTimer = setTimeout(() => {
        if (isVoiceListening && chatInput.value.trim().length > 3) {
          triggerVoiceAutoSend();
        }
      }, 1500); // 1.5 seconds of silence automatically sends message
    }
  };

  recognition.onerror = (event) => {
    console.warn("Speech recognition notice:", event.error);
    if (event.error !== "no-speech") {
      stopVoiceRecognition(false);
      if (event.error === "not-allowed" || event.error === "permission-denied") {
        alert("Microphone permission was denied. Please allow microphone access in your browser settings to use voice input.");
      }
    }
  };

  recognition.onend = () => {
    if (isVoiceListening) {
      const chatInput = document.getElementById("chatInput");
      if (chatInput && chatInput.value.trim().length > 3) {
        triggerVoiceAutoSend();
      } else {
        stopVoiceRecognition(false);
      }
    }
  };

  return recognition;
}

function triggerVoiceAutoSend() {
  if (voiceSilenceTimer) clearTimeout(voiceSilenceTimer);
  stopVoiceRecognition(true);
  const chatInput = document.getElementById("chatInput");
  if (chatInput && chatInput.value.trim().length > 0) {
    handleSendMessage();
  }
}

function toggleVoiceRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert("Voice Speech Recognition is not supported by your current browser. Please try using Google Chrome, Microsoft Edge, or Safari.");
    return;
  }

  if (isVoiceListening) {
    const chatInput = document.getElementById("chatInput");
    if (chatInput && chatInput.value.trim().length > 0) {
      triggerVoiceAutoSend();
    } else {
      stopVoiceRecognition(true);
    }
  } else {
    const chatInput = document.getElementById("chatInput");
    if (chatInput) chatInput.value = "";
    finalTranscribedText = "";

    if (!voiceRecognition) {
      voiceRecognition = initVoiceRecognition();
    }
    try {
      voiceRecognition.start();
    } catch (e) {
      voiceRecognition = initVoiceRecognition();
      if (voiceRecognition) {
        try { voiceRecognition.start(); } catch (err) {}
      }
    }
  }
}

function stopVoiceRecognition(forceStop) {
  isVoiceListening = false;
  if (voiceSilenceTimer) clearTimeout(voiceSilenceTimer);

  if (voiceRecognition && forceStop) {
    try { voiceRecognition.stop(); } catch (e) {}
  }

  const voiceBtn = document.getElementById("voiceBtn");
  const chatInput = document.getElementById("chatInput");
  if (voiceBtn) {
    voiceBtn.classList.remove("listening");
    voiceBtn.title = "Click to speak (Voice input)";
  }
  if (chatInput) {
    chatInput.placeholder = "Ask any question about admissions, fees, hostel rules, exams...";
  }
}
