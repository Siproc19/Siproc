/** @odoo-module **/

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DeliveryMapAction extends Component {
    static template = "siproc_delivery_logistics.DeliveryMapAction";

    setup() {
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({
            routeId: null,
            route: {},
            points: [],
            gpsLogs: [],
            mapReady: false,
            tracking: false,
        });

        onMounted(async () => {
            const activeId = this.props.action?.context?.active_id;
            if (!activeId) {
                this.notification.add("No se recibió una ruta activa.", { type: "danger" });
                return;
            }
            this.state.routeId = activeId;
            await this.loadRouteData();
            this.renderMap();
        });
    }

    async loadRouteData() {
        const data = await this.rpc(`/delivery/route_map_data/${this.state.routeId}`, {});
        if (!data.success) {
            this.notification.add(data.message || "Error cargando mapa", { type: "danger" });
            return;
        }
        this.state.route = data.route;
        this.state.points = data.points || [];
        this.state.gpsLogs = data.gps_logs || [];
    }

    renderMap() {
        const centerLat = this.state.route.current_latitude || 14.6349;
        const centerLng = this.state.route.current_longitude || -90.5069;

        this.map = L.map("delivery_route_map").setView([centerLat, centerLng], 12);

        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap",
        }).addTo(this.map);

        if (this.state.route.current_latitude && this.state.route.current_longitude) {
            this.vehicleMarker = L.marker([this.state.route.current_latitude, this.state.route.current_longitude])
                .addTo(this.map)
                .bindPopup("Ubicación actual del vehículo");
        }

        for (const point of this.state.points) {
            if (!point.lat || !point.lng) continue;

            let color = "orange";
            if (point.status === "delivered") color = "green";
            if (point.status === "not_found" || point.status === "rejected") color = "red";

            const icon = L.divIcon({
                className: "custom-delivery-marker",
                html: `<div style="background:${color};width:18px;height:18px;border-radius:50%;border:2px solid white;"></div>`,
                iconSize: [18, 18],
                iconAnchor: [9, 9],
            });

            L.marker([point.lat, point.lng], { icon })
                .addTo(this.map)
                .bindPopup(`
                    <b>${point.name}</b><br/>
                    ${point.address}<br/>
                    Estado: ${point.status}<br/>
                    <a href="https://www.google.com/maps?q=${point.lat},${point.lng}" target="_blank">Abrir en Google Maps</a>
                `);
        }

        const routeCoords = this.state.gpsLogs
            .filter((g) => g.lat && g.lng)
            .map((g) => [g.lat, g.lng]);

        if (routeCoords.length > 1) {
            L.polyline(routeCoords).addTo(this.map);
        }

        this.state.mapReady = true;
    }

    async takeLocationNow() {
        if (!navigator.geolocation) {
            this.notification.add("Este teléfono no soporta geolocalización.", { type: "danger" });
            return;
        }

        navigator.geolocation.getCurrentPosition(
            async (pos) => {
                await this.rpc("/delivery/update_gps", {
                    route_id: this.state.routeId,
                    latitude: pos.coords.latitude,
                    longitude: pos.coords.longitude,
                    speed: pos.coords.speed || 0,
                });
                this.notification.add("Ubicación actualizada.", { type: "success" });
                window.location.reload();
            },
            () => {
                this.notification.add("No se pudo obtener la ubicación.", { type: "danger" });
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0,
            }
        );
    }

    startTracking() {
        if (!navigator.geolocation) {
            this.notification.add("Geolocalización no soportada.", { type: "danger" });
            return;
        }

        if (this.watchId) {
            return;
        }

        this.watchId = navigator.geolocation.watchPosition(
            async (pos) => {
                await this.rpc("/delivery/update_gps", {
                    route_id: this.state.routeId,
                    latitude: pos.coords.latitude,
                    longitude: pos.coords.longitude,
                    speed: pos.coords.speed || 0,
                });
            },
            () => {
                this.notification.add("Error durante el rastreo GPS.", { type: "warning" });
            },
            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 5000,
            }
        );

        this.state.tracking = true;
        this.notification.add("Rastreo iniciado.", { type: "success" });
    }

    stopTracking() {
        if (this.watchId) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
        this.state.tracking = false;
        this.notification.add("Rastreo detenido.", { type: "info" });
    }
}

registry.category("actions").add("siproc_delivery_logistics.delivery_map", DeliveryMapAction);
