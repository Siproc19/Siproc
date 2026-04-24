/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

function lineColor(status) {
    return status === "delivered" ? "#16a34a" : status === "on_the_way" ? "#2563eb" : status === "rejected" ? "#dc2626" : "#f59e0b";
}

export class DeliveryMapAction extends Component {
    static template = "siproc_delivery_logistics.DeliveryMapAction";

    setup() {
        this.notification = useService("notification");
        this.mapRef = useRef("mapRoot");
        this.state = useState({
            routeId: null,
            route: {},
            points: [],
            plannedPath: [],
            gpsHistory: [],
            autoRefresh: true,
        });
        this.lastDeviationAlert = null;

        onMounted(async () => {
            const activeId = this.props?.action?.context?.active_id || this.props?.action?.params?.active_id || this.props?.action?.resId;
            if (!activeId) {
                this.notification.add("No se recibió una ruta activa.", { type: "danger" });
                return;
            }
            this.state.routeId = activeId;
            await this.initMap();
            await this.loadRouteData(true);
            this.refreshTimer = window.setInterval(async () => {
                if (this.state.autoRefresh) {
                    await this.loadRouteData(false);
                }
            }, 10000);
        });

        onWillUnmount(() => {
            if (this.refreshTimer) window.clearInterval(this.refreshTimer);
            if (this.map) this.map.remove();
        });
    }

    async initMap() {
        if (!this.mapRef.el) {
            this.notification.add("No se pudo montar el mapa.", { type: "danger" });
            return;
        }
        this.map = L.map(this.mapRef.el).setView([14.6349, -90.5069], 11);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap",
        }).addTo(this.map);
        this.pointLayer = L.layerGroup().addTo(this.map);
        this.routeLayer = L.layerGroup().addTo(this.map);
        this.trackingLayer = L.layerGroup().addTo(this.map);
    }

    async loadRouteData(fit = true) {
        const data = await rpc(`/delivery/route_map_data/${this.state.routeId}`, {});
        if (!data?.success) return;
        this.state.route = data.route || {};
        this.state.points = data.points || [];
        this.state.plannedPath = data.planned_path || [];
        this.state.gpsHistory = data.gps_history || [];
        this.renderMap(fit);
        this.maybeNotifyDeviation();
    }

    maybeNotifyDeviation() {
        if (!this.state.route?.deviated) return;
        const msg = this.state.route?.deviation_message || "El piloto se desvió de la ruta.";
        if (this.lastDeviationAlert !== msg) {
            this.notification.add(msg, { type: "warning", sticky: true });
            this.lastDeviationAlert = msg;
        }
    }

    renderMap(fit = true) {
        if (!this.map) return;
        this.pointLayer.clearLayers();
        this.routeLayer.clearLayers();
        this.trackingLayer.clearLayers();
        const bounds = [];

        for (const point of this.state.points) {
            if (!point.lat || !point.lng) continue;
            const ll = [point.lat, point.lng];
            bounds.push(ll);
            const marker = L.circleMarker(ll, {
                radius: 8,
                color: lineColor(point.status),
                fillColor: lineColor(point.status),
                fillOpacity: 0.85,
                weight: 2,
            }).addTo(this.pointLayer);
            marker.bindPopup(`<b>${point.sequence}. ${point.name}</b><br/>${point.address || ""}<br/>Estado: ${point.status}<br/>Tipo: ${point.stop_type}`);
        }

        if (this.state.route?.warehouse_latitude && this.state.route?.warehouse_longitude) {
            const warehouse = [this.state.route.warehouse_latitude, this.state.route.warehouse_longitude];
            bounds.push(warehouse);
            L.marker(warehouse).addTo(this.pointLayer).bindPopup("Bodega SIPROC");
        }

        if (this.state.plannedPath.length > 1) {
            L.polyline(this.state.plannedPath, { color: "#2563eb", weight: 4, opacity: 0.9 }).addTo(this.routeLayer);
        }

        if (this.state.gpsHistory.length > 1) {
            L.polyline(this.state.gpsHistory, { color: "#16a34a", weight: 5, opacity: 0.65, dashArray: "8,6" }).addTo(this.trackingLayer);
            bounds.push(...this.state.gpsHistory);
        }

        if (this.state.route.current_latitude && this.state.route.current_longitude) {
            const current = [this.state.route.current_latitude, this.state.route.current_longitude];
            bounds.push(current);
            L.circleMarker(current, { radius: 9, color: this.state.route.deviated ? "#dc2626" : "#16a34a", fillOpacity: 1 }).addTo(this.pointLayer).bindPopup("Ubicación actual del piloto");
        }

        if (fit && bounds.length) {
            this.map.fitBounds(bounds, { padding: [30, 30] });
        }
    }

    toggleAutoRefresh() {
        this.state.autoRefresh = !this.state.autoRefresh;
    }
}

registry.category("actions").add("siproc_delivery_logistics.delivery_map", DeliveryMapAction);
