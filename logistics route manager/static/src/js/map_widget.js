/** @odoo-module **/
/**
 * LogisticsMapWidget — Componente OWL del mapa interactivo para el jefe de logística.
 * Muestra rutas, posición en tiempo real del piloto y tráfico.
 * Integra Google Maps JavaScript API.
 */

import { Component, useState, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

// ─── Colores por estado de tarea ─────────────────────────────────────────────
const TASK_COLORS = {
    pending:    "#6c757d",   // Gris
    in_transit: "#ffc107",   // Amarillo
    arrived:    "#fd7e14",   // Naranja
    completed:  "#28a745",   // Verde
    failed:     "#dc3545",   // Rojo
};

const TASK_ICONS = {
    delivery: "📦",
    purchase: "🛒",
    errand:   "📋",
    bank:     "🏦",
};

// ─── Componente principal del mapa ───────────────────────────────────────────
export class LogisticsMapWidget extends Component {
    static template = "logistics_route_manager.MapWidget";
    static props = {
        routeId: { type: Number, optional: true },
        mode: { type: String, optional: true }, // 'route' | 'dashboard'
    };

    setup() {
        this.mapRef = useRef("mapContainer");
        this.notification = useService("notification");

        this.state = useState({
            map: null,
            markers: {},
            driverMarker: null,
            routePolyline: null,
            drivenPolyline: null,
            trafficLayer: null,
            showTraffic: true,
            isLoading: true,
            routeData: null,
            drivenPath: [],
        });

        this.busChannel = null;
        this.refreshInterval = null;

        onMounted(async () => {
            await this._loadGoogleMapsScript();
            await this._initMap();
            if (this.props.routeId) {
                await this._loadRouteData(this.props.routeId);
            }
            this._startRealTimeUpdates();
        });

        onWillUnmount(() => {
            this._stopRealTimeUpdates();
        });
    }

    // ── Carga del script de Google Maps ──────────────────────────────────────
    async _loadGoogleMapsScript() {
        if (window.google && window.google.maps) return;
        return new Promise((resolve, reject) => {
            // Obtener API key del backend
            rpc("/web/dataset/call_kw", {
                model: "ir.config_parameter",
                method: "get_param",
                args: ["logistics.google_maps_api_key"],
                kwargs: {},
            }).then((apiKey) => {
                if (!apiKey) {
                    console.warn("LogisticsMap: No hay API Key de Google Maps configurada.");
                    this._initLeafletFallback();
                    resolve();
                    return;
                }
                const script = document.createElement("script");
                script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=geometry,places`;
                script.async = true;
                script.defer = true;
                script.onload = resolve;
                script.onerror = () => {
                    console.warn("LogisticsMap: Error cargando Google Maps, usando Leaflet.");
                    this._initLeafletFallback();
                    resolve();
                };
                document.head.appendChild(script);
            });
        });
    }

    // ── Inicializar el mapa ───────────────────────────────────────────────────
    async _initMap() {
        if (!window.google || !window.google.maps) return;
        const mapEl = this.mapRef.el;
        if (!mapEl) return;

        this.state.map = new google.maps.Map(mapEl, {
            center: { lat: 14.6349, lng: -90.5069 }, // Guatemala City por defecto
            zoom: 12,
            mapTypeId: "roadmap",
            styles: this._getMapStyles(),
            disableDefaultUI: false,
            zoomControl: true,
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: true,
        });

        // Capa de tráfico
        this.state.trafficLayer = new google.maps.TrafficLayer();
        if (this.state.showTraffic) {
            this.state.trafficLayer.setMap(this.state.map);
        }
        this.state.isLoading = false;
    }

    // ── Cargar datos de la ruta ───────────────────────────────────────────────
    async _loadRouteData(routeId) {
        try {
            const result = await rpc(`/logistics/route/${routeId}/status`, {});
            if (result.success) {
                this.state.routeData = result.data;
                this._renderRoute(result.data);
            }
        } catch (e) {
            console.error("Error cargando ruta:", e);
        }
    }

    // ── Renderizar toda la ruta en el mapa ────────────────────────────────────
    _renderRoute(data) {
        if (!this.state.map) return;

        // Limpiar marcadores anteriores
        Object.values(this.state.markers).forEach(m => m.setMap(null));
        this.state.markers = {};

        const bounds = new google.maps.LatLngBounds();

        // Marcadores de tareas
        data.tasks.forEach((task, index) => {
            if (!task.latitude || !task.longitude) return;
            const pos = { lat: task.latitude, lng: task.longitude };
            const marker = new google.maps.Marker({
                position: pos,
                map: this.state.map,
                title: task.name,
                label: {
                    text: `${index + 1}`,
                    color: "white",
                    fontWeight: "bold",
                    fontSize: "14px",
                },
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 18,
                    fillColor: TASK_COLORS[task.state] || "#6c757d",
                    fillOpacity: 1,
                    strokeColor: "white",
                    strokeWeight: 2,
                },
            });

            // InfoWindow con detalles de la tarea
            const infoContent = `
                <div style="font-family:sans-serif; max-width:220px;">
                    <h4 style="margin:0 0 6px; font-size:14px;">${TASK_ICONS[task.task_type] || "📍"} ${task.name}</h4>
                    <p style="margin:0; font-size:12px; color:#666;">📍 ${task.address || ""}</p>
                    ${task.contact_name ? `<p style="margin:4px 0 0; font-size:12px;">👤 ${task.contact_name}</p>` : ""}
                    ${task.estimated_arrival ? `<p style="margin:4px 0 0; font-size:12px;">🕐 ETA: ${new Date(task.estimated_arrival).toLocaleTimeString("es-GT", {hour:"2-digit",minute:"2-digit"})}</p>` : ""}
                    <div style="margin-top:8px; display:flex; gap:6px;">
                        <a href="waze://?ll=${task.latitude},${task.longitude}&navigate=yes" 
                           style="background:#05C8F7;color:white;padding:4px 8px;border-radius:6px;font-size:11px;text-decoration:none;">Waze</a>
                        <a href="https://www.google.com/maps/dir/?api=1&destination=${task.latitude},${task.longitude}&travelmode=driving" 
                           target="_blank"
                           style="background:#4285F4;color:white;padding:4px 8px;border-radius:6px;font-size:11px;text-decoration:none;">GMaps</a>
                    </div>
                </div>`;
            const infoWindow = new google.maps.InfoWindow({ content: infoContent });
            marker.addListener("click", () => {
                infoWindow.open(this.state.map, marker);
            });

            this.state.markers[task.id] = marker;
            bounds.extend(pos);
        });

        // Marcador del piloto (parpadeante si está en línea)
        if (data.driver && data.driver.latitude && data.driver.longitude) {
            const driverPos = { lat: data.driver.latitude, lng: data.driver.longitude };
            if (this.state.driverMarker) {
                this.state.driverMarker.setMap(null);
            }
            this.state.driverMarker = new google.maps.Marker({
                position: driverPos,
                map: this.state.map,
                title: `🚗 ${data.driver.name}`,
                icon: {
                    url: "data:image/svg+xml;charset=UTF-8," + encodeURIComponent(`
                        <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
                            <circle cx="20" cy="20" r="18" fill="#ff6600" stroke="white" stroke-width="3"/>
                            <text x="20" y="26" text-anchor="middle" font-size="18" fill="white">🚗</text>
                        </svg>`),
                    scaledSize: new google.maps.Size(40, 40),
                    anchor: new google.maps.Point(20, 20),
                },
                zIndex: 999,
            });
            bounds.extend(driverPos);
        }

        // Ajustar el mapa a todos los marcadores
        if (!bounds.isEmpty()) {
            this.state.map.fitBounds(bounds, { padding: 40 });
        }

        // Dibujar polilínea de la ruta planificada
        if (data.polyline && window.google.maps.geometry) {
            if (this.state.routePolyline) {
                this.state.routePolyline.setMap(null);
            }
            const path = google.maps.geometry.encoding.decodePath(data.polyline.polyline);
            this.state.routePolyline = new google.maps.Polyline({
                path,
                map: this.state.map,
                strokeColor: "#4285F4",
                strokeOpacity: 0.8,
                strokeWeight: 4,
                icons: [{
                    icon: { path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW },
                    offset: "100%",
                    repeat: "80px",
                }],
            });
        }
    }

    // ── Actualizar posición del piloto ────────────────────────────────────────
    _updateDriverPosition(data) {
        if (!this.state.map || !data.latitude || !data.longitude) return;
        const pos = { lat: data.latitude, lng: data.longitude };

        // Agregar punto al historial de recorrido
        this.state.drivenPath.push(pos);

        if (this.state.driverMarker) {
            this.state.driverMarker.setPosition(pos);
        }

        // Actualizar polilínea del recorrido real
        if (this.state.drivenPolyline) {
            this.state.drivenPolyline.setMap(null);
        }
        if (this.state.drivenPath.length > 1) {
            this.state.drivenPolyline = new google.maps.Polyline({
                path: this.state.drivenPath,
                map: this.state.map,
                strokeColor: "#28a745",
                strokeOpacity: 0.6,
                strokeWeight: 3,
                strokeDasharray: "5,5",
            });
        }
    }

    // ── Actualizaciones en tiempo real via polling ────────────────────────────
    _startRealTimeUpdates() {
        if (!this.props.routeId) return;
        this.refreshInterval = setInterval(async () => {
            await this._loadRouteData(this.props.routeId);
        }, 15000); // Cada 15 segundos
    }

    _stopRealTimeUpdates() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    // ── Acciones del mapa ─────────────────────────────────────────────────────
    toggleTraffic() {
        this.state.showTraffic = !this.state.showTraffic;
        if (this.state.trafficLayer) {
            this.state.trafficLayer.setMap(this.state.showTraffic ? this.state.map : null);
        }
    }

    centerOnDriver() {
        if (this.state.driverMarker && this.state.map) {
            this.state.map.panTo(this.state.driverMarker.getPosition());
            this.state.map.setZoom(15);
        }
    }

    openAllInWaze() {
        const tasks = this.state.routeData?.tasks?.filter(t =>
            t.state !== "completed" && t.state !== "failed" && t.latitude
        );
        if (!tasks?.length) return;
        const first = tasks[0];
        window.open(`https://waze.com/ul?ll=${first.latitude},${first.longitude}&navigate=yes`, "_blank");
    }

    openAllInGoogleMaps() {
        const tasks = this.state.routeData?.tasks?.filter(t =>
            t.state !== "completed" && t.state !== "failed" && t.latitude
        );
        if (!tasks?.length) return;
        const origin = tasks[0];
        const dest = tasks[tasks.length - 1];
        const waypoints = tasks.slice(1, -1)
            .map(t => `${t.latitude},${t.longitude}`)
            .join("|");
        const url = `https://www.google.com/maps/dir/?api=1&origin=${origin.latitude},${origin.longitude}&destination=${dest.latitude},${dest.longitude}&waypoints=${waypoints}&travelmode=driving&dir_action=navigate`;
        window.open(url, "_blank");
    }

    // ── Estilos del mapa ──────────────────────────────────────────────────────
    _getMapStyles() {
        return [
            { featureType: "poi", elementType: "labels", stylers: [{ visibility: "off" }] },
            { featureType: "transit", elementType: "labels", stylers: [{ visibility: "simplified" }] },
        ];
    }

    // ── Fallback a Leaflet si no hay Google Maps API ──────────────────────────
    _initLeafletFallback() {
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
        document.head.appendChild(link);
        const script = document.createElement("script");
        script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
        script.onload = () => {
            const mapEl = this.mapRef.el;
            if (!mapEl) return;
            const map = window.L.map(mapEl).setView([14.6349, -90.5069], 12);
            window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                attribution: "© OpenStreetMap contributors",
            }).addTo(map);
            this.leafletMap = map;
            this.state.isLoading = false;
        };
        document.head.appendChild(script);
    }
}

registry.category("fields").add("logistics_map", LogisticsMapWidget);
