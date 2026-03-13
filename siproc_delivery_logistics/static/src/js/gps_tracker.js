/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

async function sendGps(routeId, latitude, longitude, speed = 0) {
    return rpc("/delivery/update_gps", {
        route_id: routeId,
        latitude: latitude,
        longitude: longitude,
        speed: speed,
    });
}

window.siprocStartGpsTracking = function (routeId, intervalMs = 60000) {
    if (!navigator.geolocation) {
        console.warn("Geolocalización no soportada por este navegador.");
        return;
    }

    const tracker = setInterval(() => {
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                try {
                    const lat = position.coords.latitude;
                    const lng = position.coords.longitude;
                    const speed = position.coords.speed || 0;
                    const result = await sendGps(routeId, lat, lng, speed);
                    console.log("GPS enviado:", result);
                } catch (error) {
                    console.error("Error enviando GPS:", error);
                }
            },
            (error) => {
                console.error("Error obteniendo GPS:", error);
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0,
            }
        );
    }, intervalMs);

    window.siprocGpsTrackerInterval = tracker;
    console.log("Tracking GPS iniciado para ruta:", routeId);
};

window.siprocStopGpsTracking = function () {
    if (window.siprocGpsTrackerInterval) {
        clearInterval(window.siprocGpsTrackerInterval);
        window.siprocGpsTrackerInterval = null;
        console.log("Tracking GPS detenido");
    }
};
