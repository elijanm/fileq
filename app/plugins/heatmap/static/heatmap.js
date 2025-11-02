// --- Load check ---
if (typeof h337 === "undefined") {
  console.error("❌ Heatmap.js not loaded. Check CDN or connection.");
} else {
  console.log("✅ Heatmap.js loaded successfully");
}

// --- Heatmap initialization ---
const heatmapInstance = h337.create({
  container: document.querySelector("#heatmapContainer"),
  radius: 25,
  maxOpacity: 0.6,
  blur: 0.85,
  backgroundColor: "rgba(0,0,0,0)",
});

// --- Utility to send events to Service Worker ---
function sendToSW(type, data = {}) {
  if (navigator.serviceWorker.controller) {
    console.log("sw");
    navigator.serviceWorker.controller.postMessage({
      type: "HEATMAP_EVENT",
      data: {
        ...data,
        event_type: type,
        t: Date.now(),
        url: location.href,
        viewport: {
          w: window.innerWidth,
          h: window.innerHeight,
        },
      },
    });
  } else {
    console.log("controller");
  }
}

// --- 1. Mouse movement ---
document.addEventListener("mousemove", (e) => {
  const event = { x: e.clientX, y: e.clientY, value: 1 };
  heatmapInstance.addData(event);
  sendToSW("mousemove", event);
});

// --- 2. Mouse clicks ---
document.addEventListener("click", (e) => {
  sendToSW("click", {
    x: e.clientX,
    y: e.clientY,
    button: e.button,
  });
});

// --- 3. Scroll events ---
window.addEventListener("scroll", () => {
  const scrollDepth =
    window.scrollY / (document.body.scrollHeight - window.innerHeight);
  sendToSW("scroll", {
    scrollY: window.scrollY,
    depth: Number(scrollDepth.toFixed(3)),
  });
});

// --- 4. Keypress / keyboard activity ---
document.addEventListener("keydown", (e) => {
  sendToSW("keydown", {
    key: e.key,
    code: e.code,
  });
});

// --- 5. Window focus / blur ---
window.addEventListener("focus", () => sendToSW("focus"));
window.addEventListener("blur", () => sendToSW("blur"));

// --- 6. Page visibility (tab switching) ---
document.addEventListener("visibilitychange", () => {
  sendToSW(
    document.visibilityState === "hidden" ? "tab_hidden" : "tab_visible"
  );
});

// --- 7. Resize events ---
window.addEventListener("resize", () => {
  sendToSW("resize", {
    w: window.innerWidth,
    h: window.innerHeight,
  });
});

// --- 8. Initial session info ---
sendToSW("session_start", {
  referrer: document.referrer,
  userAgent: navigator.userAgent,
  lang: navigator.language,
  tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
});

// --- 9. Unload event (flush before leaving) ---
window.addEventListener("beforeunload", () => sendToSW("session_end"));

// --- Register Service Worker ---
if ("serviceWorker" in navigator) {
  navigator.serviceWorker
    .register("/heatmap/static/sw.js", { scope: "/" })
    .then((r) => {
      console.log("[SW] Registered at", r.scope);
      return navigator.serviceWorker.ready;
    })
    .then(() => console.log("[SW] Ready and controlling page"))
    .catch(console.error);
}
