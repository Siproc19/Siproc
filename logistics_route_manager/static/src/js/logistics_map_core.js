/** @odoo-module **/

/**
 * Utilidades compartidas por el mapa de ruta y la Torre de Control.
 *
 * Los iconos se construyen con `L.divIcon` (HTML puro) en vez de los
 * marcadores por defecto de Leaflet: así el módulo no depende de los PNG
 * de Leaflet y no hay imágenes rotas.
 */

export const OSM_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
export const OSM_ATTRIBUTION =
    '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';

/** Color de cada estado de parada. */
export const TASK_COLORS = {
    pending: "#6c757d",
    in_transit: "#0dcaf0",
    arrived: "#ffc107",
    completed: "#198754",
    failed: "#dc3545",
};

/** Color de cada estado de conexión GPS. */
export const GPS_STATUS = {
    online: { color: "#198754", label: "En línea" },
    delay: { color: "#ffc107", label: "Con retraso" },
    offline: { color: "#dc3545", label: "Sin señal" },
};

const VEHICLE_GLYPH = {
    motorcycle: "🏍️",
    car: "🚗",
    pickup: "🛻",
    van: "🚐",
    truck: "🚚",
};

/**
 * Comprueba que Leaflet esté disponible. Si no lo está, deja un mensaje
 * claro en el estado del componente en vez de fallar en silencio.
 */
export function ensureLeaflet(state) {
    if (typeof L === "undefined") {
        state.loading = false;
        state.error =
            "No se pudo cargar la librería de mapas. Actualiza la lista de aplicaciones y recarga la página.";
        return false;
    }
    return true;
}

/** Marcador del piloto: círculo con el glifo del vehículo y halo de estado. */
export function driverIcon(isOnline, vehicleType) {
    const color = isOnline ? GPS_STATUS.online.color : GPS_STATUS.offline.color;
    const glyph = VEHICLE_GLYPH[vehicleType] || "🚗";
    return L.divIcon({
        className: "o_logistics_driver_icon",
        html: `<div class="o_logistics_driver_pin" style="border-color:${color};">
                   <span>${glyph}</span>
                   <i style="background:${color};"></i>
               </div>`,
        iconSize: [38, 38],
        iconAnchor: [19, 19],
        popupAnchor: [0, -20],
    });
}

/** Marcador de parada: círculo numerado con el color de su estado. */
export function stopIcon(position, color) {
    return L.divIcon({
        className: "o_logistics_stop_icon",
        html: `<div class="o_logistics_stop_pin" style="background:${color};">${position}</div>`,
        iconSize: [26, 26],
        iconAnchor: [13, 13],
        popupAnchor: [0, -14],
    });
}

/**
 * Decodifica una polilínea codificada de Google (la que devuelve la
 * Directions API) a una lista de pares [lat, lng] para Leaflet.
 */
export function decodePolyline(encoded) {
    if (!encoded) {
        return [];
    }
    const points = [];
    let index = 0;
    let lat = 0;
    let lng = 0;

    while (index < encoded.length) {
        let result = 0;
        let shift = 0;
        let byte;
        do {
            byte = encoded.charCodeAt(index++) - 63;
            result |= (byte & 0x1f) << shift;
            shift += 5;
        } while (byte >= 0x20);
        lat += result & 1 ? ~(result >> 1) : result >> 1;

        result = 0;
        shift = 0;
        do {
            byte = encoded.charCodeAt(index++) - 63;
            result |= (byte & 0x1f) << shift;
            shift += 5;
        } while (byte >= 0x20);
        lng += result & 1 ? ~(result >> 1) : result >> 1;

        points.push([lat / 1e5, lng / 1e5]);
    }
    return points;
}

/** Escapa texto que se inyecta en los popups de Leaflet. */
export function escapeHtml(value) {
    return String(value === undefined || value === null ? "" : value).replace(
        /[<>&"]/g,
        (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])
    );
}
