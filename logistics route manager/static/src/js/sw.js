/**
 * sw.js — Service Worker para la PWA del piloto.
 * Permite uso básico offline y caché de assets estáticos.
 */

const CACHE_NAME = "logipiloto-v1";
const STATIC_ASSETS = [
    "/logistics/driver/app",
    "/logistics_route_manager/static/src/css/mobile_driver.css",
    "/logistics_route_manager/static/src/js/gps_tracker.js",
    "/logistics_route_manager/static/src/js/driver_app.js",
];

// Instalación: cachear assets estáticos
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS).catch((e) => {
                console.warn("SW: Error cacheando algunos assets:", e);
            });
        })
    );
    self.skipWaiting();
});

// Activación: limpiar caches antiguos
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
            )
        )
    );
    self.clients.claim();
});

// Fetch: strategy "network first, fallback to cache"
self.addEventListener("fetch", (event) => {
    const url = new URL(event.request.url);

    // Para endpoints de API (GPS, tareas): solo network, sin cache
    if (url.pathname.startsWith("/logistics/gps") ||
        url.pathname.startsWith("/logistics/task")) {
        event.respondWith(fetch(event.request));
        return;
    }

    // Para assets estáticos: cache first
    if (url.pathname.startsWith("/logistics_route_manager/static")) {
        event.respondWith(
            caches.match(event.request).then((cached) =>
                cached || fetch(event.request).then((response) => {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                    return response;
                })
            )
        );
        return;
    }

    // Para el resto: network first, fallback a cache
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                const clone = response.clone();
                caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                return response;
            })
            .catch(() => caches.match(event.request))
    );
});
