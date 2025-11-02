// AFHSync Chat - Main JavaScript

// WebSocket Connection
let ws;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

// DOM Elements
const messagesContainer = document.getElementById("messagesContainer");
const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");
const typingIndicator = document.getElementById("typingIndicator");
const statusText = document.getElementById("statusText");
const connectionStatus = document.getElementById("connectionStatus");
const themeBtn = document.getElementById("themeBtn");
const themeModal = document.getElementById("themeModal");
const closeModal = document.getElementById("closeModal");

// Theme Management
const themes = ["green", "blue", "purple", "pink", "dark", "teal"];
let currentTheme = document.body.className.replace("theme-", "") || "green";

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  connectWebSocket();
  setupEventListeners();
  loadThemePreference();
});

// Add after DOMContentLoaded
// In static/js/chat.js - Add after DOMContentLoaded

// Parse URL parameters for context
const urlParams = new URLSearchParams(window.location.search);
const contextParam = urlParams.get("context");

if (contextParam) {
  const contextBanner = document.getElementById("contextBanner");
  const contextName = document.getElementById("contextName");
  const contextDetails = document.getElementById("contextDetails");

  const contextInfo = {
    caregiver: {
      icon: "👩‍⚕️",
      title: "Caregiver Portal",
      detail: "Find jobs and build your career",
    },
    afh_provider: {
      icon: "🏠",
      title: "AFH Owner Portal",
      detail: "Manage facilities and hire staff",
    },
    service_provider: {
      icon: "🛠️",
      title: "Service Provider Portal",
      detail: "Connect with AFH clients",
    },
  };

  if (contextInfo[contextParam]) {
    const info = contextInfo[contextParam];
    document.querySelector(".context-icon").textContent = info.icon;
    contextName.textContent = info.title;
    contextDetails.textContent = info.detail;
    contextBanner.style.display = "flex";
  }
}

let heartbeatInterval;

function startHeartbeat() {
  // Send ping every 5 minutes to refresh session TTL
  heartbeatInterval = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "ping" }));
      console.log("Heartbeat sent");
    }
  }, 300000); // 5 minutes
}

function stopHeartbeat() {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
  }
}
// WebSocket Functions
function connectWebSocket() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log("✅ WebSocket connected");
    reconnectAttempts = 0;
    updateStatus("Online", true);
    sendButton.disabled = false;
    startHeartbeat();
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "pong") {
      console.log("Heartbeat acknowledged");
      return;
    }
    if (data.type === "bot_response") {
      hideTyping();
      addMessage(data.message, "bot");
    } else if (data.type === "error") {
      hideTyping();
      addMessage("Sorry, an error occurred. Please try again.", "bot");
    }
  };

  ws.onerror = (error) => {
    console.error("❌ WebSocket error:", error);
    updateStatus("Connection error", false);
  };

  ws.onclose = () => {
    console.log("🔌 WebSocket closed");
    updateStatus("Disconnected", false);
    sendButton.disabled = true;
    stopHeartbeat();

    if (reconnectAttempts < maxReconnectAttempts) {
      connectionStatus.classList.add("show");
      reconnectAttempts++;
      const delay = 2000 * reconnectAttempts;
      setTimeout(connectWebSocket, delay);
    } else {
      connectionStatus.querySelector(".status-text").textContent =
        "Connection lost. Please refresh the page.";
    }
  };
}

// Message Functions
function addMessage(text, type) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${type}-message`;

  const now = new Date();
  const timeStr = now.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });

  messageDiv.innerHTML = `
        <div class="message-content">
            <div class="message-bubble">
                <div class="message-text">${formatMessageText(text)}</div>
                <div class="message-time">${timeStr}</div>
            </div>
        </div>
    `;

  // Remove "Connecting..." message if it exists
  const firstBotMessage = messagesContainer.querySelector(".bot-message");
  if (firstBotMessage && firstBotMessage.textContent.includes("Connecting")) {
    firstBotMessage.remove();
  }

  messagesContainer.insertBefore(messageDiv, typingIndicator);
  scrollToBottom();
}

// In static/js/chat.js - Add link click handler

function formatMessageText(text) {
  const escapeHtml = (unsafe) => {
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  };

  text = escapeHtml(text);
  text = text.replace(/\n/g, "<br>");

  // Convert URLs to links
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  text = text.replace(
    urlRegex,
    '<a href="$1" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: underline;">$1</a>'
  );

  // Convert action links [text](#action:action_name)
  const actionLinkRegex = /\[([^\]]+)\]\(#action:([^\)]+)\)/g;
  text = text.replace(
    actionLinkRegex,
    '<a href="#" class="action-link" data-action="$2" style="color: var(--primary-color); text-decoration: none; font-weight: 500; display: inline-block; padding: 8px 0; border-bottom: 2px solid transparent; transition: border-color 0.2s;">$1</a>'
  );

  // Convert bold **text**
  text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  // Convert italic *text*
  text = text.replace(/\*([^*]+)\*/g, "<em>$1</em>");

  // Convert numbered lists
  text = text.replace(
    /^(\d+)\.\s+(.+)$/gm,
    '<div style="margin-left: 10px;">$1. $2</div>'
  );

  return text;
}

// Add event delegation for action links
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("action-link")) {
    e.preventDefault();
    const action = e.target.dataset.action;
    handleActionLink(action);
  }
});

function handleActionLink(action) {
  // Map action IDs to what the bot expects
  const actionMessages = {
    // Preferences - send simplified values the bot can match
    pref_pets_yes: "love pets",
    pref_pets_no: "no pets",
    pref_pets_depends: "depends",

    pref_house_quiet: "quiet",
    pref_house_active: "active",
    pref_house_none: "no preference",

    lang_english: "english only",
    lang_multiple: "multiple",

    mobility_heavy: "50",
    mobility_light: "25",
    mobility_limited: "limited",
    mobility_none: "companionship",

    transport_vehicle: "vehicle",
    transport_transit: "transit",
    transport_need: "need",

    shift_day: "day",
    shift_evening: "evening",
    shift_night: "night",
    shift_livein: "live-in",
    shift_flexible: "flexible",

    care_dementia: "dementia",
    care_diabetes: "diabetes",
    care_hospice: "hospice",
    care_surgery: "surgery",
    care_stroke: "stroke",
    care_none: "none",

    diet_all: "all",
    diet_basic: "basic",
    diet_none: "no",

    // Service menu
    browse_jobs: "browse jobs",
    resume_builder: "resume",
    complete_profile: "preferences",
    upload_certs: "upload",
    update_availability: "availability",
    view_applications: "applications",

    // Navigation
    menu: "menu",
    show_all_jobs: "no",
    more_jobs: "more",

    // Role selection
    select_role_caregiver: "caregiver",
    select_role_afh: "afh provider",
    select_role_service: "service provider",
  };

  // Get display text for user message bubble
  const displayText = getDisplayTextForAction(action);

  // Get what to send to bot
  const botMessage = actionMessages[action] || action.replace(/_/g, " ");

  // Show user what they clicked
  addMessage(displayText, "user");

  // Send bot-parseable value
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(
      JSON.stringify({
        type: "user_message",
        message: botMessage,
      })
    );
    showTyping();
  }
}

function getDisplayTextForAction(action) {
  // What user sees in their message bubble
  const displayMap = {
    pref_pets_yes: "Yes - I love pets",
    pref_pets_no: "No - Allergies or discomfort",
    pref_pets_depends: "Depends on the type/size",
    pref_house_quiet: "Quiet and calm",
    pref_house_active: "Active and busy",
    pref_house_none: "No preference",
    mobility_heavy: "Yes - Can lift 50+ lbs",
    mobility_light: "Yes - Can lift up to 25 lbs",
    mobility_limited: "Limited - Prefer non-physical care",
    mobility_none: "No lifting - Companionship only",
    transport_vehicle: "Yes - Own vehicle",
    transport_transit: "Yes - Public transit",
    transport_need: "Need transportation assistance",
    shift_day: "Day shifts",
    shift_evening: "Evening shifts",
    shift_night: "Night shifts",
    shift_livein: "Live-in care",
    shift_flexible: "Flexible - Any shift",
    browse_jobs: "Browse job openings",
    resume_builder: "Build your resume",
    complete_profile: "Complete job preferences",
    menu: "Return to menu",
  };

  return displayMap[action] || action.replace(/_/g, " ");
}
// function handleActionLink(action) {
//   // Map actions to user messages
//   const actionMessages = {
//     browse_jobs: "I want to browse job openings",
//     resume_builder: "I want to build my resume",
//     complete_profile: "I want to complete my profile",
//     upload_certs: "I want to upload certifications",
//     update_availability: "I want to update my availability",
//     view_applications: "Show me my applications",
//     update_profile: "I want to update my profile",

//     // AFH Provider
//     upload_photos: "I want to upload facility photos",
//     post_job: "I want to post a job opening",
//     add_facility: "I want to add another facility",
//     facility_details: "I want to complete facility details",
//     browse_caregivers: "Show me available caregivers",
//     manage_postings: "I want to manage my job postings",
//     review_applications: "Show me applications",

//     // Service Provider
//     upload_brochures: "I want to upload service brochures",
//     upload_portfolio: "I want to upload photos",
//     set_pricing: "I want to set my pricing",
//     browse_requests: "Show me AFH requests",
//     list_services: "I want to list my services",
//     manage_offerings: "I want to manage my offerings",
//     update_pricing: "I want to update pricing",

//     // Role selection
//     select_role_caregiver: "1",
//     select_role_afh: "2",
//     select_role_service: "3",
//   };

//   const message = actionMessages[action] || action.replace(/_/g, " ");

//   // Add user message
//   addMessage(message, "user");

//   // Send to bot
//   if (ws.readyState === WebSocket.OPEN) {
//     ws.send(
//       JSON.stringify({
//         type: "user_message",
//         message: message,
//       })
//     );
//     showTyping();
//   }
// }

function showTyping() {
  typingIndicator.classList.add("active");
  scrollToBottom();
}

function hideTyping() {
  typingIndicator.classList.remove("active");
}

function scrollToBottom() {
  setTimeout(() => {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }, 100);
}

function sendMessage() {
  const message = messageInput.value.trim();
  if (!message || ws.readyState !== WebSocket.OPEN) return;

  addMessage(message, "user");

  ws.send(
    JSON.stringify({
      type: "user_message",
      message: message,
    })
  );

  messageInput.value = "";
  showTyping();
  messageInput.focus();
}

function updateStatus(text, online) {
  const statusDot = statusText.querySelector(".status-dot");
  const statusSpan = statusText.querySelector("span");

  if (statusSpan) {
    statusSpan.textContent = text;
  }

  if (statusDot) {
    statusDot.style.background = online ? "#4caf50" : "#f44336";
  }

  if (online) {
    connectionStatus.classList.remove("show");
  }
}

// Theme Functions
function loadThemePreference() {
  const savedTheme = localStorage.getItem("chatTheme");
  if (savedTheme && themes.includes(savedTheme)) {
    setTheme(savedTheme);
  }
}

function setTheme(theme) {
  document.body.className = `theme-${theme}`;
  currentTheme = theme;
  localStorage.setItem("chatTheme", theme);

  // Update active state in theme picker
  document.querySelectorAll(".theme-option").forEach((option) => {
    option.classList.remove("active");
    if (option.dataset.theme === theme) {
      option.classList.add("active");
    }
  });
}

// Event Listeners
function setupEventListeners() {
  // Send message
  sendButton.addEventListener("click", sendMessage);

  messageInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Enable/disable send button based on input
  messageInput.addEventListener("input", () => {
    sendButton.disabled =
      !messageInput.value.trim() || ws.readyState !== WebSocket.OPEN;
  });

  // Theme button
  themeBtn.addEventListener("click", () => {
    themeModal.classList.add("show");
  });

  // Close modal
  closeModal.addEventListener("click", () => {
    themeModal.classList.remove("show");
  });

  // Click outside modal to close
  themeModal.addEventListener("click", (e) => {
    if (e.target === themeModal) {
      themeModal.classList.remove("show");
    }
  });

  // Escape key to close modal
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && themeModal.classList.contains("show")) {
      themeModal.classList.remove("show");
    }
  });

  // Theme options
  document.querySelectorAll(".theme-option").forEach((option) => {
    option.addEventListener("click", () => {
      setTheme(option.dataset.theme);
      setTimeout(() => {
        themeModal.classList.remove("show");
      }, 300);
    });
  });

  // Auto-focus input on mobile
  if (window.innerWidth <= 768) {
    messageInput.focus();
  }

  // Prevent zoom on input focus (iOS)
  messageInput.addEventListener("focus", () => {
    if (window.innerWidth <= 768) {
      document.body.style.zoom = "100%";
    }
  });
}

// Utility Functions
function playNotificationSound() {
  // Optional: Add sound notification for new messages
  try {
    const audio = new Audio("/static/sounds/notification.mp3");
    audio.volume = 0.3;
    audio.play().catch((e) => console.log("Audio play prevented:", e));
  } catch (e) {
    // Sound not available
  }
}

// Visibility API - Pause/Resume when tab is hidden/visible
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    console.log("Tab hidden");
  } else {
    console.log("Tab visible");
    scrollToBottom();
  }
});

// Service Worker for PWA (optional)
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("static/js/sw.js")
      .then((reg) => console.log("Service Worker registered"))
      .catch((err) => console.log("Service Worker registration failed"));
  });
}
