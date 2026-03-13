/** @odoo-module **/

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

export class DeliveryMapAction extends Component {
    static template = "siproc_delivery_logistics.DeliveryMapAction";

    setup() {
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            routeId: null,
            route: {},
            points: [],
        });

        onMounted(async () => {
            try {
                const activeId =
                    this.props?.action?.context?.active_id ||
                    this.props?.action?.params?.active_id ||
                    this.props?.action?.resId;

                if (!activeId) {
                    this.notification.add("No se recibió una ruta activa.", {
                        type: "danger",
                    });
                    return;
                }

                this.state.routeId = activeId;
                await this.loadRouteData();
                this.renderMap();
            } catch (error) {
                console.error("Error al cargar mapa:", error);
                this.notification.add("Error al cargar el mapa.", {
                    type: "danger",
                });
            }
        });
    }

    async loadRouteData() {
        const data = await rpc(`/delivery/route_map_data/${this.state.routeId}`, {});
        if (!data || !data.success) {
            this.notification.add(
                (data && data.message) || "Error cargando datos del mapa",
                { type: "danger" }
            );
            return;
        }

        this.state.route = data.route || {};
        this.state.points = data.points || [];
    }

    renderMap() {
        if (typeof L === "undefined") {
            this.notification.add("Leaflet no está cargado.", { type: "danger" });
            return;
        }

        const mapContainer = document.getElementById("delivery_route_map");
        if (!mapContainer) {
            this.notification.add("No se encontró el contenedor del mapa.", {
                type: "danger",
            });
            return;
        }

        if (this.map) {
            this.map.remove();
        }

        const lat = this.state.route.current_latitude || 14.6349;
        const lng = this.state.route.current_longitude || -90.5069;

        this.map = L.map("delivery_route_map").setView([lat, lng], 12);

        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap",
        }).addTo(this.map);

        if (this.state.route.current_latitude && this.state.route.current_longitude) {
            L.marker([this.state.route.current_latitude, this.state.route.current_longitude])
                .addTo(this.map)
                .bindPopup("Ubicación actual");
        }

        for (const point of this.state.points) {
            if (!point.lat || !point.lng) continue;

            L.marker([point.lat, point.lng])
                .addTo(this.map)
                .bindPopup(`
                    <b>${point.name || "Entrega"}</b><br/>
                    ${point.address || ""}<br/>
                    Estado: ${point.status || "pending"}
                `);
        }
    }

    async takeLocationNow() {
        this.notification.add("Función Tomar ubicación aún en construcción.", {
            type: "info",
        });
    }

    startTracking() {
        this.notification.add("Función Iniciar rastreo aún en construcción.", {
            type: "info",
        });
    }

    stopTracking() {
        this.notification.add("Función Detener rastreo aún en construcción.", {
            type: "info",
        });
    }
}

registry.category("actions").add(
    "siproc_delivery_logistics.delivery_map",
    DeliveryMapAction
);
