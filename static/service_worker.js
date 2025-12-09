const CACHE_NAME = "expense-cache-v1";

// Files to cache on install
const ASSETS_TO_CACHE = [
    "/",
    "/history",
    "/add_expense",
    "/reports",
    "/static/css/styles.css",
    "/static/js/main.js",
    "/static/icons/icon-192.png",
    "/static/icons/icon-512.png"
];

// Install Event - caching assets
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(ASSETS_TO_CACHE))
            .then(() => self.skipWaiting())
    );
});

// Activate Event - clean up old caches
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) return caches.delete(key);
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch Event - cache-first with network update
self.addEventListener("fetch", (event) => {
    if (event.request.method !== "GET") return; // only cache GET requests

    event.respondWith(
        caches.match(event.request).then((cached) => {
            const fetchPromise = fetch(event.request)
                .then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, networkResponse.clone());
                        });
                    }
                    return networkResponse;
                })
                .catch(() => cached); // fallback to cache if network fails

            return cached || fetchPromise;
        })
    );
});
