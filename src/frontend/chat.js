
const API_CHAT = "http://localhost:8000";

let sessionId = null;        // backend session ID
let chatInitialized = false;
let currentSearchResults = [];

function buildChatPopup() {
  if (document.getElementById("chat-popup")) return;

  const popup = document.createElement("div");
  popup.id = "chat-popup";
  popup.innerHTML = `
    <div id="chat-popup-header" onclick="toggleChat()">
      <div style="display:flex;align-items:center;gap:8px;">
        <span id="chat-status-dot"></span>
        <div>
          <div id="chat-popup-title">مساعد فرص خضراء</div>
          <div id="chat-popup-sub">اسألني عن أي فرصة من النتائج</div>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <span id="chat-unread-badge" style="display:none;">1</span>
        <button id="chat-toggle-btn" aria-label="تصغير المحادثة">
          <i class="ti ti-chevron-down"></i>
        </button>
      </div>
    </div>
    <div id="chat-popup-body">
      <div id="chat-popup-messages"></div>
      <div id="chat-popup-input-row">
        <input
          id="chat-popup-input"
          type="text"
          placeholder="اسألني عن الفرص..."
          autocomplete="off"
          onkeydown="if(event.key==='Enter') sendPopupChat()"
          dir="rtl"
        />
        <button onclick="sendPopupChat()" id="chat-popup-send-btn" aria-label="إرسال">
          <i class="ti ti-send"></i>
        </button>
      </div>
    </div>
  `;

  document.body.appendChild(popup);
  injectChatStyles();
}

/* ── Inject styles ── */
function injectChatStyles() {
  if (document.getElementById("chat-popup-styles")) return;
  const style = document.createElement("style");
  style.id = "chat-popup-styles";
  style.textContent = `
    #chat-popup {
      position: fixed;
      bottom: 24px;
      left: 24px;
      width: 360px;
      border-radius: 16px;
      background: #ffffff;
      border: 1px solid #e0e0e0;
      box-shadow: 0 8px 32px rgba(0,0,0,0.14);
      z-index: 9999;
      font-family: 'Segoe UI', Arial, sans-serif;
      direction: rtl;
      overflow: hidden;
      transition: transform 0.25s ease, opacity 0.25s ease;
    }
    #chat-popup.minimized #chat-popup-body { display: none; }
    #chat-popup.minimized #chat-toggle-btn i { transform: rotate(180deg); }
    #chat-popup-header {
      background: #F5A000;;
      padding: 12px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      user-select: none;
    }
    #chat-status-dot {
      width: 9px; height: 9px;
      border-radius: 50%;
      background: #3aaa6a;
      flex-shrink: 0;
    }
    #chat-popup-title { font-size: 14px; font-weight: 700; color: #ffffff; }
    #chat-popup-sub { font-size: 11px; color: rgba(255,255,255,0.75); margin-top: 1px; }
    #chat-toggle-btn {
      background: none; border: none; color: #ffffff;
      cursor: pointer; padding: 4px; font-size: 18px;
      display: flex; align-items: center;
    }
    #chat-toggle-btn i { transition: transform 0.25s ease; }
    #chat-unread-badge {
      background: #F5A000; color: #fff;
      font-size: 11px; font-weight: 700;
      border-radius: 99px; padding: 1px 7px;
      min-width: 20px; text-align: center;
    }
    #chat-popup-body { display: flex; flex-direction: column; }
    #chat-popup-messages {
      padding: 12px 14px;
      display: flex; flex-direction: column; gap: 8px;
      height: 320px; overflow-y: auto; scroll-behavior: smooth;
    }
    .popup-msg {
      max-width: 88%; padding: 9px 13px;
      font-size: 13px; line-height: 1.6;
      border-radius: 14px; white-space: pre-wrap; word-break: break-word;
    }
    .popup-msg-bot {
      align-self: flex-end;
      background: #f0faf4; border: 1px solid #d4eddf;
      color: #0f4d28; border-radius: 14px 14px 4px 14px;
    }
    .popup-msg-user {
      align-self: flex-start;
      background: #f7f7f7; color: #2a2a2a;
      border-radius: 14px 14px 14px 4px;
    }
    .popup-msg-loading {
      align-self: flex-end; font-size: 12px; color: #9e9e9e;
      padding: 7px 13px; background: #f0f0f0; border-radius: 14px;
      animation: pulse 1s infinite;
    }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
    #chat-popup-input-row {
      display: flex; gap: 8px; padding: 10px 12px;
      border-top: 1px solid #efefef; background: #fff;
    }
    #chat-popup-input {
      flex: 1; padding: 9px 13px;
      border: 1px solid #dedede; border-radius: 8px;
      font-size: 13px; direction: rtl; color: #2a2a2a;
      background: #fff; outline: none; font-family: inherit;
      transition: border-color 0.2s;
    }
    #chat-popup-input:focus {
      border-color: #3aaa6a;
      box-shadow: 0 0 0 3px rgba(58,170,106,0.12);
    }
    #chat-popup-send-btn {
      padding: 9px 13px; background: #F5A000; color: #fff;
      border: none; border-radius: 8px; cursor: pointer;
      font-size: 15px; display: flex; align-items: center;
      transition: background 0.15s;
    }
    #chat-popup-send-btn:hover { background: #1a7a3f; }
    #chat-popup-send-btn:disabled { background: #dedede; cursor: not-allowed; }
    #chat-launcher {
      position: fixed; bottom: 24px; left: 24px;
      width: 56px; height: 56px; border-radius: 50%;
      background: #1a7a3f; color: #fff; border: none;
      cursor: pointer; font-size: 24px;
      display: none; align-items: center; justify-content: center;
      box-shadow: 0 4px 16px rgba(26,122,63,0.35);
      z-index: 9999; transition: transform 0.15s;
    }
    #chat-launcher:hover { transform: scale(1.08); background: #0f4d28; }
    @media (max-width: 480px) {
      #chat-popup { width: calc(100vw - 32px); left: 16px; bottom: 16px; }
    }
  `;
  document.head.appendChild(style);
}

/* launcher button*/
function buildLauncher() {
  if (document.getElementById("chat-launcher")) return;
  const btn = document.createElement("button");
  btn.id = "chat-launcher";
  btn.setAttribute("aria-label", "فتح المساعد الذكي");
  btn.innerHTML = `<i class="ti ti-message-chatbot"></i>`;
  btn.onclick = openChat;
  document.body.appendChild(btn);
}

function toggleChat() {
  const popup = document.getElementById("chat-popup");
  popup.classList.toggle("minimized");
  if (!popup.classList.contains("minimized")) {
    document.getElementById("chat-unread-badge").style.display = "none";
  }
}

function openChat() {
  document.getElementById("chat-launcher").style.display = "none";
  const popup = document.getElementById("chat-popup");
  popup.style.display = "block";
  popup.classList.remove("minimized");
  document.getElementById("chat-popup-input").focus();
}

/* called from search.js after results load */
function initChatWithResults(results) {
  currentSearchResults = results;
  buildChatPopup();
  buildLauncher();

  const popup = document.getElementById("chat-popup");
  popup.style.display = "block";
  popup.classList.remove("minimized");

  const messagesDiv = document.getElementById("chat-popup-messages");

  if (!chatInitialized) {
    chatInitialized = true;
    messagesDiv.innerHTML = "";
    addPopupMessage(
      `مرحباً!  وجدت ${results.length} فرصة لك. اسألني عن أي منها بالعربية أو الإنجليزية!`,
      "bot"
    );
  } else {
    addPopupMessage(
      `تم تحديث النتائج — الآن لدي ${results.length} فرصة. اسألني عنها!`,
      "bot"
    );
    const popup = document.getElementById("chat-popup");
    if (popup.classList.contains("minimized")) {
      document.getElementById("chat-unread-badge").style.display = "inline-block";
    }
  }

  document.getElementById("chat-popup-input").focus();
}

/* append a message bubble*/
function addPopupMessage(text, role) {
  const box = document.getElementById("chat-popup-messages");
  if (!box) return;
  const div = document.createElement("div");
  div.className = role === "user" ? "popup-msg popup-msg-user" : "popup-msg popup-msg-bot";
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return div;
}

function showPopupLoading() {
  const box = document.getElementById("chat-popup-messages");
  const div = document.createElement("div");
  div.className = "popup-msg-loading";
  div.id = "popup-loader";
  div.textContent = "يفكر...";
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function hidePopupLoading() {
  const loader = document.getElementById("popup-loader");
  if (loader) loader.remove();
}

/* send message */
async function sendPopupChat() {
  const input = document.getElementById("chat-popup-input");
  const btn   = document.getElementById("chat-popup-send-btn");
  const message = input.value.trim();
  if (!message) return;

  input.value = "";
  btn.disabled = true;

  addPopupMessage(message, "user");
  showPopupLoading();

  try {
    const res = await fetch(`${API_CHAT}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,   // null on first message → backend creates new session
        message: message
      }),
    });

    hidePopupLoading();

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const data = await res.json();

    // saving session_id from backend for all future messages
    sessionId = data.session_id;

    addPopupMessage(data.answer || "عذراً، لم أتمكن من الإجابة.", "bot");

    // Show unread badge if minimized
    const popup = document.getElementById("chat-popup");
    if (popup && popup.classList.contains("minimized")) {
      document.getElementById("chat-unread-badge").style.display = "inline-block";
    }

  } catch (err) {
    hidePopupLoading();
    addPopupMessage("خطأ في الاتصال — تأكد من تشغيل uvicorn main:app", "bot");
    console.error("Chat error:", err);
  } finally {
    btn.disabled = false;
    input.focus();
  }
}