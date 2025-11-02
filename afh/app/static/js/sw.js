// Service Worker for AFHSync Chat
const CACHE_NAME = "afhsync-v1";
const urlsToCache = [
  "/static/css/chat.css",
  "/static/css/themes.css",
  "/static/js/chat.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache))
  );
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches
      .match(event.request)
      .then((response) => response || fetch(event.request))
  );
});
