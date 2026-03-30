/** @odoo-module **/
/**
 * route_optimizer.js — Utilidades de optimización de rutas en el frontend.
 */

import { rpc } from "@web/core/network/rpc";

/**
 * Abre la ruta completa en Google Maps con todas las paradas como waypoints.
 * @param {Array} tasks - Lista de tareas con latitude y longitude
 */
export function openFullRouteGoogleMaps(tasks) {
    const validTasks = tasks.filter(t =>
        t.latitude && t.longitude &&
        t.state !== "completed" && t.state !== "failed"
    );
    if (validTasks.length === 0) {
        alert("No hay paradas con coordenadas disponibles.");
        return;
    }
    if (validTasks.length === 1) {
        const t = validTasks[0];
        window.open(
            `https://www.google.com/maps/dir/?api=1&destination=${t.latitude},${t.longitude}&travelmode=driving&dir_action=navigate`,
            "_blank"
        );
        return;
    }
    const origin      = `${validTasks[0].latitude},${validTasks[0].longitude}`;
    const destination = `${validTasks[validTasks.length-1].latitude},${validTasks[validTasks.length-1].longitude}`;
    const waypoints   = validTasks.slice(1, -1)
        .map(t => `${t.latitude},${t.longitude}`)
        .join("|");
    const url = `https://www.google.com/maps/dir/?api=1` +
                `&origin=${origin}` +
                `&destination=${destination}` +
                `${waypoints ? "&waypoints=" + waypoints : ""}` +
                `&travelmode=driving&dir_action=navigate`;
    window.open(url, "_blank");
}

/**
 * Abre la primera parada pendiente en Waze.
 * Nota: Waze Deep Link solo soporta 1 destino a la vez.
 * @param {Object} task - Tarea con latitude, longitude y name
 */
export function openTaskInWaze(task) {
    if (!task.latitude || !task.longitude) {
        alert("Esta tarea no tiene coordenadas GPS.");
        return;
    }
    const name     = encodeURIComponent(task.name || "");
    const wazeNative = `waze://?ll=${task.latitude},${task.longitude}&navigate=yes&q=${name}`;
    const wazeWeb    = `https://waze.com/ul?ll=${task.latitude},${task.longitude}&navigate=yes&q=${name}`;
    window.location.href = wazeNative;
    setTimeout(() => window.open(wazeWeb, "_blank"), 1500);
}

/**
 * Calcula la distancia en metros entre dos puntos GPS (Haversine).
 */
export function haversineDistance(lat1, lon1, lat2, lon2) {
    const R = 6371000;
    const toRad = (x) => (x * Math.PI) / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
        Math.sin(dLat / 2) ** 2 +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.asin(Math.sqrt(a));
}
