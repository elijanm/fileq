console.log("[SW] Loaded");

const DB_NAME = "HeatmapAnalytics";
const STORE_NAME = "events";
const ENDPOINT = self.origin + "/heatmap/api/analytics/heatmap";

const BATCH_SIZE = 50; // Max events before writing to DB
const FLUSH_INTERVAL = 10_000; // Flush every 10 seconds

let sessionId = crypto.randomUUID();
let inMemoryBatch = [];

// --- LIFECYCLE EVENTS ---
self.addEventListener("install", (event) => {
  console.log("[SW] Installed");
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  console.log("[SW] Activated");
  event.waitUntil(self.clients.claim());
});

// --- INDEXEDDB HELPERS ---
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onerror = () => reject(req.error);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { autoIncrement: true });
      }
    };
    req.onsuccess = () => resolve(req.result);
  });
}

function txDone(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function addToQueue(events) {
  const db = await openDB();
  const tx = db.transaction(STORE_NAME, "readwrite");
  const store = tx.objectStore(STORE_NAME);
  for (const e of events) store.add(e);
  await txDone(tx);
}

async function getAllEvents() {
  const db = await openDB();
  const tx = db.transaction(STORE_NAME, "readonly");
  const store = tx.objectStore(STORE_NAME);
  return new Promise((resolve) => {
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result || []);
  });
}

async function clearQueue() {
  const db = await openDB();
  const tx = db.transaction(STORE_NAME, "readwrite");
  tx.objectStore(STORE_NAME).clear();
  await txDone(tx);
}

// --- MAIN FLUSH FUNCTION ---
async function flushQueue() {
  // Push pending memory batch into DB
  if (inMemoryBatch.length) {
    console.log(`[SW] 🧩 Committing ${inMemoryBatch.length} in-memory events`);
    await addToQueue(inMemoryBatch.splice(0));
  }

  const events = await getAllEvents();
  if (!events.length) return;

  console.log(`[SW] 🚀 Flushing ${events.length} events to server...`);

  try {
    const payload = {
      session_id: sessionId,
      ts: Date.now(),
      events,
    };

    const res = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      console.log(`[SW] ✅ Flushed ${events.length} events`);
      await clearQueue();
    } else {
      console.warn(`[SW] ⚠️ Server responded ${res.status}`);
    }
  } catch (err) {
    console.warn("[SW] ❌ Flush failed (offline?):", err);
  }
}

// --- HANDLE INCOMING EVENTS ---
self.addEventListener("message", async (event) => {
  const { type, data } = event.data || {};

  if (type === "HEATMAP_EVENT" && data) {
    const entry = {
      session_id: sessionId,
      event_type: data.event_type,
      payload: data,
      received_at: Date.now(),
    };
    console.log(entry);
    inMemoryBatch.push(entry);

    // Commit to IndexedDB when batch threshold reached
    if (inMemoryBatch.length >= BATCH_SIZE) {
      console.log(`[SW] 💾 Batch reached ${BATCH_SIZE}, writing to DB`);
      await addToQueue(inMemoryBatch.splice(0));
    }
  }
});

// --- AUTO-FLUSH LOOP ---
setInterval(flushQueue, FLUSH_INTERVAL);

// --- BACKGROUND SYNC SUPPORT ---
self.addEventListener("sync", (event) => {
  if (event.tag === "flush-heatmap") {
    event.waitUntil(flushQueue());
  }
});
