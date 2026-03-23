/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

function lineColor(status) {
    return status === 'delivered' ? '#16a34a' : status === 'on_the_way' ? '#2563eb' : '#f59e0b';
}

export class DeliveryMapAction extends Component {
    static template = "siproc_delivery_logistics.DeliveryMapAction";

    setup() {
        this.notification = useService("notification");
        this.state = useState({ routeId: null, route: {}, points: [], autoRefresh: true });
        onMounted(async () => {
            const activeId = this.props?.action?.context?.active_id || this.props?.action?.params?.active_id || this.props?.action?.resId;
            if (!activeId) {
                this.notification.add("No se recibió una ruta activa.", { type: "danger" });
                return;
            }
            this.state.routeId = activeId;
            this.map = L.map(this.refs.mapRoot).setView([14.6349, -90.5069], 11);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(this.map);
            this.pointLayer = L.layerGroup().addTo(this.map);
            this.routeLayer = L.layerGroup().addTo(this.map);
            await this.loadRouteData();
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

    async loadRouteData(fit=true) {
        const data = await rpc(`/delivery/route_map_data/${this.state.routeId}`, {});
        if (!data?.success) return;
        this.state.route = data.route || {};
        this.state.points = data.points || [];
        this.renderMap(fit);
    }

    renderMap(fit=true) {
        if (!this.map) return;
        this.pointLayer.clearLayers();
        this.routeLayer.clearLayers();
        const latlngs = [];
        for (const point of this.state.points) {
            if (!point.lat || !point.lng) continue;
            const ll = [point.lat, point.lng];
            latlngs.push(ll);
            const marker = L.circleMarker(ll, { radius: 8, color: lineColor(point.status), fillOpacity: 0.8 }).addTo(this.pointLayer);
            marker.bindPopup(`<b>${point.sequence}. ${point.name}</b><br/>${point.address || ''}<br/>Estado: ${point.status}<br/>Tipo: ${point.stop_type}`);
        }
        if (this.state.route.current_latitude && this.state.route.current_longitude) {
            const current = [this.state.route.current_latitude, this.state.route.current_longitude];
            latlngs.push(current);
            L.marker(current).addTo(this.pointLayer).bindPopup('Ubicación actual del piloto');
        }
        if (latlngs.length > 1) {
            L.polyline(latlngs, { color: '#2563eb', weight: 4 }).addTo(this.routeLayer);
        }
        if (fit && latlngs.length) {
            this.map.fitBounds(latlngs, { padding: [30, 30] });
        }
    }

    toggleAutoRefresh() { this.state.autoRefresh = !this.state.autoRefresh; }
}

registry.category("actions").add("siproc_delivery_logistics.delivery_map", DeliveryMapAction);
