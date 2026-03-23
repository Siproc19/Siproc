/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
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

function gpsStatus(lastGpsDatetime) {
    if (!lastGpsDatetime) {
        return { label: "Sin señal", color: "#ef4444" };
    }
    const last = new Date(lastGpsDatetime);
    const now = new Date();
    const diffSec = Math.floor((now - last) / 1000);
    if (diffSec <= 45) {
        return { label: "En línea", color: "#16a34a" };
    }
    if (diffSec <= 180) {
        return { label: "Con retraso", color: "#d97706" };
    }
    return { label: "Sin señal", color: "#ef4444" };
}

export class DeliveryMapAction extends Component {
    static template = "siproc_delivery_logistics.DeliveryMapAction";

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.state = useState({
            routeId: null,
            route: {},
            points: [],
            selectedPointIndex: null,
            mapUrl: buildEmbedUrl(),
            tracking: false,
            adminAutoRefresh: true,
            gpsStatusLabel: "Sin señal",
            gpsStatusColor: "#ef4444",
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

            this.refreshTimer = window.setInterval(async () => {
                if (this.state.adminAutoRefresh && this.state.routeId) {
                    await this.loadRouteData(false);
                }
            }, 5000);
        });

        onWillUnmount(() => {
            if (this.watchId) {
                navigator.geolocation.clearWatch(this.watchId);
                this.watchId = null;
            }
            if (this.refreshTimer) {
                window.clearInterval(this.refreshTimer);
                this.refreshTimer = null;
            }
        });
    }

    async loadRouteData(resetFocus = true) {
        const data = await rpc(`/delivery/route_map_data/${this.state.routeId}`, {});
        if (!data || !data.success) {
            this.notification.add((data && data.message) || "Error cargando datos del mapa", {
                type: "danger",
            });
            return;
        }
        this.state.route = data.route || {};
        this.state.points = data.points || [];

        const status = gpsStatus(this.state.route.last_gps_datetime);
        this.state.gpsStatusLabel = status.label;
        this.state.gpsStatusColor = status.color;

        const selected = this.state.selectedPointIndex !== null ? this.state.points[this.state.selectedPointIndex] : null;
        if (!resetFocus && selected) {
            return;
        }

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

    toggleAutoRefresh() {
        this.state.adminAutoRefresh = !this.state.adminAutoRefresh;
        this.notification.add(
            this.state.adminAutoRefresh ? "Actualización automática activada." : "Actualización automática detenida.",
            { type: "info" }
        );
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
                    delivery_line_id: this.state.route.current_task_id || false,
                });
                this.notification.add("Ubicación actualizada.", { type: "success" });
                await this.loadRouteData();
            },
            () => this.notification.add("No se pudo obtener la ubicación.", { type: "danger" }),
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    }

    async toggleServerTracking(active) {
        const method = active ? "action_resume_tracking" : "action_stop_tracking";
        await this.orm.call("delivery.route", method, [[this.state.routeId]]);
        await this.loadRouteData(false);
    }

    startTracking() {
        if (!navigator.geolocation) {
            this.notification.add("Este teléfono no soporta geolocalización.", { type: "danger" });
            return;
        }
        if (this.watchId) {
            return;
        }
        this.toggleServerTracking(true);
        this.watchId = navigator.geolocation.watchPosition(
            async (pos) => {
                await rpc("/delivery/update_gps", {
                    route_id: this.state.routeId,
                    latitude: pos.coords.latitude,
                    longitude: pos.coords.longitude,
                    speed: pos.coords.speed || 0,
                    delivery_line_id: this.state.route.current_task_id || false,
                });
                this.state.tracking = true;
                await this.loadRouteData(false);
            },
            () => this.notification.add("No se pudo rastrear la ubicación.", { type: "warning" }),
            { enableHighAccuracy: true, timeout: 12000, maximumAge: 1000 }
        );
        this.notification.add("Rastreo iniciado.", { type: "success" });
    }

    stopTracking() {
        if (this.watchId) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
        this.toggleServerTracking(false);
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
