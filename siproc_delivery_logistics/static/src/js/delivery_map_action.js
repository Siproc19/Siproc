/** @odoo-module **/

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

function buildEmbedUrl(lat, lng) {
    if (!lat || !lng) {
        return "https://www.openstreetmap.org/export/embed.html?bbox=-90.6,14.5,-90.4,14.7&layer=mapnik";
    }
    const delta = 0.01;
    const left = lng - delta;
    const right = lng + delta;
    const top = lat + delta;
    const bottom = lat - delta;
    return `https://www.openstreetmap.org/export/embed.html?bbox=${left},${bottom},${right},${top}&layer=mapnik&marker=${lat},${lng}`;
}

export class DeliveryMapAction extends Component {
    static template = "siproc_delivery_logistics.DeliveryMapAction";

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            routeId: null,
            route: {},
            points: [],
            selectedPointIndex: null,
            mapUrl: buildEmbedUrl(),
            tracking: false,
        });

        onMounted(async () => {
            const activeId =
                this.props?.action?.context?.active_id ||
                this.props?.action?.params?.active_id ||
                this.props?.action?.resId;

            if (!activeId) {
                this.notification.add("No se recibió una ruta activa.", { type: "danger" });
                return;
            }

            this.state.routeId = activeId;
            await this.loadRouteData();
        });
    }

    async loadRouteData() {
        const data = await rpc(`/delivery/route_map_data/${this.state.routeId}`, {});
        if (!data || !data.success) {
            this.notification.add((data && data.message) || "Error cargando datos del mapa", {
                type: "danger",
            });
            return;
        }
        this.state.route = data.route || {};
        this.state.points = data.points || [];

        const lat = this.state.route.current_latitude || this.state.points[0]?.lat;
        const lng = this.state.route.current_longitude || this.state.points[0]?.lng;
        this.state.mapUrl = buildEmbedUrl(lat, lng);
    }

    selectPoint(point, index) {
        this.state.selectedPointIndex = index;
        this.state.mapUrl = buildEmbedUrl(point.lat, point.lng);
    }

    focusCurrentRoute() {
        const lat = this.state.route.current_latitude || this.state.points[0]?.lat;
        const lng = this.state.route.current_longitude || this.state.points[0]?.lng;
        this.state.selectedPointIndex = null;
        this.state.mapUrl = buildEmbedUrl(lat, lng);
    }

    async takeLocationNow() {
        if (!navigator.geolocation) {
            this.notification.add("Este teléfono no soporta geolocalización.", { type: "danger" });
            return;
        }
        navigator.geolocation.getCurrentPosition(
            async (pos) => {
                await rpc("/delivery/update_gps", {
                    route_id: this.state.routeId,
                    latitude: pos.coords.latitude,
                    longitude: pos.coords.longitude,
                    speed: pos.coords.speed || 0,
                });
                this.notification.add("Ubicación actualizada.", { type: "success" });
                await this.loadRouteData();
            },
            () => this.notification.add("No se pudo obtener la ubicación.", { type: "danger" }),
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    }

    startTracking() {
        if (!navigator.geolocation) {
            this.notification.add("Este teléfono no soporta geolocalización.", { type: "danger" });
            return;
        }
        if (this.watchId) {
            return;
        }
        this.watchId = navigator.geolocation.watchPosition(
            async (pos) => {
                await rpc("/delivery/update_gps", {
                    route_id: this.state.routeId,
                    latitude: pos.coords.latitude,
                    longitude: pos.coords.longitude,
                    speed: pos.coords.speed || 0,
                });
                this.state.tracking = true;
            },
            () => this.notification.add("No se pudo rastrear la ubicación.", { type: "warning" }),
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 }
        );
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

    openGoogleMaps() {
        const selected = this.state.selectedPointIndex !== null ? this.state.points[this.state.selectedPointIndex] : null;
        const url = selected?.google_maps_url || this.state.route.google_maps_url;
        if (url) {
            window.open(url, "_blank");
        }
    }

    openWaze() {
        const selected = this.state.selectedPointIndex !== null ? this.state.points[this.state.selectedPointIndex] : null;
        const url = selected?.waze_url || this.state.route.waze_url;
        if (url) {
            window.open(url, "_blank");
        }
    }
}

registry.category("actions").add("siproc_delivery_logistics.delivery_map", DeliveryMapAction);
