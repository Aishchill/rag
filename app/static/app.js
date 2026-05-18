// ── Upload handling ────────────────────────────────────────────────────
const fileInput = document.getElementById("fileInput");
const uploadForm = document.getElementById("uploadForm");
const uploadProgress = document.getElementById("uploadProgress");
const uploadBody = document.querySelector(".upload-body");

if (fileInput) {
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      uploadBody.style.display = "none";
      uploadProgress.style.display = "flex";
      uploadForm.submit();
    }
  });

  // Drag-and-drop
  const zone = document.getElementById("uploadZone");
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.style.borderColor = "var(--accent)"; });
  zone.addEventListener("dragleave", () => { zone.style.borderColor = ""; });
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) {
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInput.files = dt.files;
      fileInput.dispatchEvent(new Event("change"));
    }
  });
}

// ── Chat handling ──────────────────────────────────────────────────────
const chatWindow = document.getElementById("chatWindow");
const questionInput = document.getElementById("questionInput");
const askBtn = document.getElementById("askBtn");
const askBtnText = document.getElementById("askBtnText");
const askSpinner = document.getElementById("askSpinner");

function appendBubble(role, text, sources, isHtml = false) {
  const welcome = chatWindow.querySelector(".chat-welcome");
  if (welcome) welcome.remove();

  const wrap = document.createElement("div");
  wrap.className = `chat-bubble ${role}`;

  const content = document.createElement("div");
  content.className = "bubble-content";
  if (isHtml) {
    content.innerHTML = text;
  } else {
    content.textContent = text;
  }
  wrap.appendChild(content);

  if (sources && sources.length > 0) {
    const src = document.createElement("div");
    src.className = "bubble-sources";
    src.innerHTML = "Sources: " + sources.map(s =>
      `<span class="source-tag">📄 ${s}</span>`
    ).join("");
    wrap.appendChild(src);
  }

  chatWindow.appendChild(wrap);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function askQuestion() {
  if (!questionInput) return;
  const question = questionInput.value.trim();
  if (!question) return;

  appendBubble("user", question);
  questionInput.value = "";
  askBtn.disabled = true;
  askBtnText.style.display = "none";
  askSpinner.style.display = "inline-block";

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    if (data.error) {
      appendBubble("ai", "Error: " + data.error, null, false);
    } else {
      appendBubble("ai", data.answer_html || data.answer, data.sources, true);
    }
  } catch {
    appendBubble("ai", "Network error. Please try again.", null, false);
  } finally {
    askBtn.disabled = false;
    askBtnText.style.display = "inline";
    askSpinner.style.display = "none";
  }
}

if (questionInput) {
  questionInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askQuestion();
    }
  });
}
