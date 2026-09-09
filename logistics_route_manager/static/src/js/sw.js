/**
 * sw.js — Service Worker de la PWA del piloto.
 *
 * Este archivo NO se sirve directo desde /static: lo sirve el controlador
 * en /logistics/sw.js, que sustituye __VERSION_CACHE__ por la versión
 * instalada del módulo. Así, cada vez que se actualiza el módulo cambia el
 * nombre de la caché y el teléfono descarta sola la versión anterior.
 *
 * La versión anterior de este archivo tenía dos fallas graves:
 *
 *   1. El nombre de la caché era fijo ("logipiloto-v1"), así que la
 *      limpieza del evento `activate` nunca borraba nada.
 *   2. Los archivos .js se servían con estrategia «caché primero», o sea
 *      que ni siquiera se intentaba pedirle al servidor la versión nueva.
 *
 * Juntas hacían que el teléfono se quedara para siempre con el JavaScript
 * que guardó el primer día. Las correcciones se publicaban en el servidor
 * y nunca llegaban al piloto.
 */

const CACHE_NAME = "logipiloto-__VERSION_CACHE__";

// Solo para que la app abra sin señal. El contenido fresco siempre se
// pide primero a la red.
const RESPALDO_OFFLINE = [
    "/logistics/driver/app",
    "/logistics_route_manager/static/src/css/mobile_driver.css",
    "/logistics_route_manager/static/src/js/gps_tracker.js",
    "/logistics_route_manager/static/src/js/driver_app.js",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(RESPALDO_OFFLINE))
            .catch((e) => console.warn("SW: no se pudo precachear:", e))
    );
    // Tomar el control sin esperar a que se cierren las pestañas viejas.
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then((nombres) => Promise.all(
                nombres
                    .filter((n) => n.startsWith("logipiloto-") && n !== CACHE_NAME)
                    .map((n) => caches.delete(n))
            ))
            .then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", (event) => {
    const req = event.request;
    const url = new URL(req.url);

    // Solo se atiende lo del propio dominio y en GET.
    if (req.method !== "GET" || url.origin !== self.location.origin) return;

    // Los endpoints de datos nunca se cachean.
    if (url.pathname.startsWith("/logistics/gps") ||
        url.pathname.startsWith("/logistics/task") ||
        url.pathname.startsWith("/logistics/route") ||
        url.pathname.startsWith("/web/session")) {
        return;
    }

    // Todo lo demás: RED PRIMERO. La caché es solo el paracaídas para
    // cuando el piloto se queda sin señal.
    event.respondWith(
        fetch(req)
            .then((respuesta) => {
                if (respuesta && respuesta.ok) {
                    const copia = respuesta.clone();
                    caches.open(CACHE_NAME).then((c) => c.put(req, copia));
                }
                return respuesta;
            })
            .catch(() => caches.match(req))
    );
});
