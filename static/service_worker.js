self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open("expense-cache").then((cache) => {
            return cache.addAll([
                "/",
                "/history",
                "/add_expense",
                "/reports",
                "/static/css/styles.css",
                "/static/js/main.js"
            ]);
        })
    );
    self.skipWaiting();
});

self.addEventListener("fetch", (event) => {
    event.respondWith(
        caches.match(event.request).then((cached) => {
            return cached || fetch(event.request);
        })
    );
});
