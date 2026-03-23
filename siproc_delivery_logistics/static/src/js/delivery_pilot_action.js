/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

export class DeliveryPilotAction extends Component {
    static template = "siproc_delivery_logistics.DeliveryPilotAction";
    setup() {
        this.notification = useService("notification");
        this.state = useState({ routeId: null, route: {}, points: [], selectedLineId: null, tracking: false, photoData: null, photoName: null });
        onMounted(async () => {
            const activeId = this.props?.action?.context?.active_id || this.props?.action?.params?.active_id || this.props?.action?.resId;
            this.state.routeId = activeId;
            this.map = L.map(this.refs.mapRoot).setView([14.6349, -90.5069], 11);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; OpenStreetMap' }).addTo(this.map);
            this.pointLayer = L.layerGroup().addTo(this.map);
            await this.loadRoute();
            this.startTracking();
        });
        onWillUnmount(() => {
            if (this.watchId) navigator.geolocation.clearWatch(this.watchId);
            if (this.sendTimer) clearInterval(this.sendTimer);
            if (this.map) this.map.remove();
        });
    }
    get activePoint() {
        return this.state.points.find((p) => p.id === this.state.selectedLineId) || this.state.points.find((p) => ['pending','on_the_way','rescheduled'].includes(p.status)) || this.state.points[0];
    }
    async loadRoute() {
        const data = await rpc(`/delivery/route_map_data/${this.state.routeId}`, {});
        if (!data?.success) return;
        this.state.route = data.route || {};
        this.state.points = data.points || [];
        this.state.selectedLineId = this.state.route.active_line_id || this.activePoint?.id;
        this.renderMap();
    }
    renderMap() {
        this.pointLayer.clearLayers();
        const latlngs = [];
        for (const p of this.state.points) {
            if (!(p.lat && p.lng)) continue;
            const ll = [p.lat, p.lng]; latlngs.push(ll);
            const marker = L.marker(ll).addTo(this.pointLayer);
            marker.bindPopup(`<b>${p.sequence}. ${p.name}</b><br/>${p.address || ''}`);
        }
        if (this.state.route.current_latitude && this.state.route.current_longitude) {
            latlngs.push([this.state.route.current_latitude, this.state.route.current_longitude]);
            L.circleMarker([this.state.route.current_latitude, this.state.route.current_longitude], { radius: 8, color: '#16a34a' }).addTo(this.pointLayer).bindPopup('Tu ubicación actual');
        }
        if (latlngs.length) this.map.fitBounds(latlngs, { padding: [30, 30] });
    }
    async sendGpsNow() {
        if (!navigator.geolocation) return;
        return new Promise((resolve) => {
            navigator.geolocation.getCurrentPosition(async (pos) => {
                await rpc('/delivery/update_gps', {
                    route_id: this.state.routeId,
                    latitude: pos.coords.latitude,
                    longitude: pos.coords.longitude,
                    speed: pos.coords.speed || 0,
                    delivery_line_id: this.activePoint?.id || false,
                });
                await this.loadRoute();
                resolve();
            }, () => resolve(), { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
        });
    }
    startTracking() {
        if (this.state.tracking) return;
        this.state.tracking = true;
        this.sendGpsNow();
        const intervalMs = Math.max(10, this.state.route.gps_interval_seconds || 15) * 1000;
        this.sendTimer = setInterval(() => this.sendGpsNow(), intervalMs);
        this.notification.add('Rastreo GPS activo.', { type: 'success' });
    }
    stopTracking() {
        if (this.sendTimer) clearInterval(this.sendTimer);
        this.state.tracking = false;
        this.notification.add('Rastreo GPS detenido.', { type: 'info' });
    }
    choosePoint(id) { this.state.selectedLineId = id; }
    onFileChange(ev) {
        const file = ev.target.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => { this.state.photoData = reader.result; this.state.photoName = file.name; };
        reader.readAsDataURL(file);
    }
    async pointAction(action) {
        if (!this.activePoint) return;
        await this.sendGpsNow();
        const res = await rpc('/delivery/line_action', {
            line_id: this.activePoint.id,
            action,
            photo_base64: action === 'delivered' ? this.state.photoData : false,
            photo_filename: action === 'delivered' ? (this.state.photoName || 'evidencia.jpg') : false,
        });
        if (!res?.success) {
            this.notification.add(res?.message || 'No se pudo actualizar el punto.', { type: 'danger' });
            return;
        }
        this.state.photoData = null;
        this.state.photoName = null;
        await this.loadRoute();
        this.notification.add(res.message || 'Punto actualizado.', { type: 'success' });
    }
    openNav(kind) {
        const point = this.activePoint;
        const url = kind === 'waze' ? point?.waze_url : point?.google_maps_url;
        if (url) window.open(url, '_blank');
    }
}
registry.category('actions').add('siproc_delivery_logistics.delivery_pilot', DeliveryPilotAction);
