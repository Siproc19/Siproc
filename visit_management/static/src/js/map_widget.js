/** @odoo-module **/
/**
 * visit_management/static/src/js/map_widget.js
 * Widget de Geolocalización GPS para Visitas Comerciales
 * Compatible con Odoo 19 / OWL
 */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";

/**
 * Componente OWL para capturar coordenadas GPS del dispositivo
 * y mostrar el mapa con la ubicación del cliente y del asesor.
 */
export class GpsCapture extends Component {
    static template = "visit_management.GpsCapture";
    static props = {
        visitId:         { type: Number,   optional: true },
        clientLat:       { type: Number,   optional: true },
        clientLng:       { type: Number,   optional: true },
        onLocationCaptured: { type: Function, optional: true },
    };

    setup() {
        this.notification = useService("notification");
        this.rpc          = useService("rpc");
        this.mapRef       = useRef("mapContainer");

        this.state = useState({
            capturing:  false,
            latitude:   null,
            longitude:  null,
            address:    "",
            accuracy:   null,
            distance:   null,
            gpsValid:   false,
            error:      null,
        });

        this.map         = null;
        this.userMarker  = null;
        this.clientMarker = null;

        onMounted(() => this._initMap());
        onWillUnmount(() => this._destroyMap());
    }

    // ─── Inicializar Mapa (OpenStreetMap via Leaflet) ──────────────
    _initMap() {
        const container = this.mapRef.el;
        if (!container) return;

        // Carga dinámica de Leaflet si no está disponible
        if (typeof L === "undefined") {
            this._loadLeaflet().then(() => this._buildMap(container));
        } else {
            this._buildMap(container);
        }
    }

    async _loadLeaflet() {
        // Cargar CSS de Leaflet
        const link = document.createElement("link");
        link.rel   = "stylesheet";
        link.href  = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
        document.head.appendChild(link);

        // Cargar JS de Leaflet
        await new Promise((resolve, reject) => {
            const script    = document.createElement("script");
            script.src      = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
            script.onload   = resolve;
            script.onerror  = reject;
            document.head.appendChild(script);
        });
    }

    _buildMap(container) {
        const defaultLat = this.props.clientLat || 4.7110;
        const defaultLng = this.props.clientLng || -74.0721;

        this.map = L.map(container).setView([defaultLat, defaultLng], 15);

        // Tiles OpenStreetMap
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom:     19,
            attribution: "© OpenStreetMap contributors",
        }).addTo(this.map);

        // Marcador del cliente
        if (this.props.clientLat && this.props.clientLng) {
            const clientIcon = L.divIcon({
                html:      '<div style="background:#e74c3c;width:20px;height:20px;border-radius:50%;border:3px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3)"></div>',
                iconSize:  [20, 20],
                className: "",
            });
            this.clientMarker = L.marker(
                [this.props.clientLat, this.props.clientLng],
                { icon: clientIcon }
            )
            .bindPopup("📍 Ubicación del Cliente")
            .addTo(this.map);
        }
    }

    _destroyMap() {
        if (this.map) {
            this.map.remove();
            this.map = null;
        }
    }

    // ─── Capturar GPS del dispositivo ─────────────────────────────
    async captureGps() {
        if (!navigator.geolocation) {
            this.notification.add(
                "Tu navegador no soporta geolocalización.",
                { type: "danger" }
            );
            return;
        }

        this.state.capturing = true;
        this.state.error     = null;

        try {
            const position = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, {
                    enableHighAccuracy: true,
                    timeout:            15000,
                    maximumAge:         0,
                });
            });

            const { latitude, longitude, accuracy } = position.coords;
            this.state.latitude  = latitude;
            this.state.longitude = longitude;
            this.state.accuracy  = accuracy;

            // Calcular distancia al cliente
            if (this.props.clientLat && this.props.clientLng) {
                this.state.distance = this._haversine(
                    latitude, longitude,
                    this.props.clientLat, this.props.clientLng
                );
                this.state.gpsValid = this.state.distance <= 200;
            }

            // Geocodificación inversa (OpenStreetMap Nominatim)
            try {
                const res = await fetch(
                    `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`
                );
                const data = await res.json();
                this.state.address = data.display_name || "";
            } catch (_) {
                this.state.address = `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`;
            }

            // Actualizar mapa
            if (this.map) {
                const userIcon = L.divIcon({
                    html:      '<div style="background:#3498db;width:16px;height:16px;border-radius:50%;border:3px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3)"></div>',
                    iconSize:  [16, 16],
                    className: "",
                });
                if (this.userMarker) {
                    this.userMarker.setLatLng([latitude, longitude]);
                } else {
                    this.userMarker = L.marker([latitude, longitude], { icon: userIcon })
                        .bindPopup("🔵 Tu ubicación actual")
                        .addTo(this.map);
                }

                // Ajustar zoom para ver ambos marcadores
                if (this.clientMarker) {
                    const group = L.featureGroup([this.userMarker, this.clientMarker]);
                    this.map.fitBounds(group.getBounds().pad(0.2));
                } else {
                    this.map.setView([latitude, longitude], 16);
                }

                // Dibujar línea entre puntos
                if (this.props.clientLat && this.props.clientLng) {
                    L.polyline(
                        [[latitude, longitude], [this.props.clientLat, this.props.clientLng]],
                        { color: "#3498db", weight: 3, dashArray: "6,6" }
                    ).addTo(this.map);
                }
            }

            // Callback al componente padre
            if (this.props.onLocationCaptured) {
                this.props.onLocationCaptured({
                    latitude,
                    longitude,
                    accuracy,
                    address: this.state.address,
                });
            }

            this.notification.add("📍 Ubicación GPS capturada correctamente.", { type: "success" });

        } catch (err) {
            let msg = "Error al obtener ubicación GPS.";
            if (err.code === 1) msg = "Permiso de ubicación denegado. Por favor, permite el acceso al GPS.";
            if (err.code === 2) msg = "No se pudo determinar la ubicación. Verifica tu conexión GPS.";
            if (err.code === 3) msg = "Tiempo de espera agotado. Intenta de nuevo.";

            this.state.error = msg;
            this.notification.add(msg, { type: "danger" });
        } finally {
            this.state.capturing = false;
        }
    }

    // ─── Fórmula Haversine (distancia en metros) ──────────────────
    _haversine(lat1, lon1, lat2, lon2) {
        const R    = 6371000;
        const phi1 = (lat1 * Math.PI) / 180;
        const phi2 = (lat2 * Math.PI) / 180;
        const dphi = ((lat2 - lat1) * Math.PI) / 180;
        const dlam = ((lon2 - lon1) * Math.PI) / 180;
        const a    = Math.sin(dphi / 2) ** 2
                   + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlam / 2) ** 2;
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    }
}

// Template OWL inline
GpsCapture.template = "visit_management.GpsCapture";

// Registrar el componente
registry.category("view_widgets").add("gps_capture", GpsCapture);
