/** @odoo-module **/

/**
 * Torre de Control — vista de Gerencia y Jefatura de Bodega.
 *
 * Un solo mapa con TODOS los pilotos y vehículos del día, más un panel
 * lateral con el estado de cada ruta y las alertas activas.
 *
 * Los datos vienen de `logistics.route.get_control_tower_data`, que
 * respeta las reglas de registro: un piloto solo se ve a sí mismo.
 */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import {
    GPS_STATUS,
    driverIcon,
    ensureLeaflet,
    escapeHtml,
    OSM_URL,
    OSM_ATTRIBUTION,
} from "./logistics_map_core";

const REFRESH_MS = 15000;
const GUATEMALA_CITY = [14.6349, -90.5069];

export class ControlTower extends Component {
    static template = "logistics_route_manager.ControlTower";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.mapRef = useRef("map");

        this.state = useState({
            loading: true,
            error: "",
            date: "",
            fleet: [],
            alerts: [],
            summary: {
                routes: 0,
                in_progress: 0,
                online: 0,
                offline: 0,
                deviated: 0,
                total_tasks: 0,
                completed_tasks: 0,
                progress: 0,
            },
            selectedRouteId: null,
            filter: "all", // all | online | offline | deviated
            lastRefresh: "",
        });

        this.map = null;
        this.markers = {}; // route_id -> L.Marker
        this.timer = null;
        this.resizeObserver = null;

        onMounted(() => this.initMap());
        onWillUnmount(() => this.teardown());
    }

    async initMap() {
        if (!ensureLeaflet(this.state)) {
            return;
        }
        this.map = L.map(this.mapRef.el, { zoomControl: true }).setView(
            GUATEMALA_CITY,
            11
        );
        L.tileLayer(OSM_URL, {
            maxZoom: 19,
            attribution: OSM_ATTRIBUTION,
        }).addTo(this.map);

        // El panel lateral y las alertas cambian la altura disponible: se
        // recalcula el tamaño del mapa una vez estabilizado el layout.
        setTimeout(() => this.map && this.map.invalidateSize(), 250);
        this.resizeObserver = new ResizeObserver(() => {
            if (this.map) {
                this.map.invalidateSize();
            }
        });
        this.resizeObserver.observe(this.mapRef.el);

        await this.refresh(true);
        this.timer = setInterval(() => this.refresh(false), REFRESH_MS);
    }

    teardown() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }
        if (this.map) {
            this.map.remove();
            this.map = null;
        }
    }

    async refresh(fitBounds) {
        let data;
        try {
            data = await this.orm.call(
                "logistics.route",
                "get_control_tower_data",
                [],
                {}
            );
        } catch (error) {
            this.state.error =
                "No se pudo cargar el estado de la flota. Verifica tus permisos de Logística.";
            this.state.loading = false;
            return;
        }

        this.state.loading = false;
        this.state.error = "";
        this.state.date = data.date;
        this.state.fleet = data.fleet;
        this.state.alerts = data.alerts;
        this.state.summary = data.summary;
        this.state.lastRefresh = new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        });

        this.drawFleet(data.fleet);
        if (fitBounds) {
            this.fitAll();
        }
    }

    drawFleet(fleet) {
        const seen = new Set();

        fleet.forEach((unit) => {
            if (!unit.latitude || !unit.longitude) {
                return;
            }
            seen.add(unit.route_id);
            const latlng = [unit.latitude, unit.longitude];
            const icon = driverIcon(unit.gps_status === "online", unit.vehicle_type);

            let marker = this.markers[unit.route_id];
            if (marker) {
                marker.setLatLng(latlng);
                marker.setIcon(icon);
            } else {
                marker = L.marker(latlng, { icon }).addTo(this.map);
                marker.on("click", () => {
                    this.state.selectedRouteId = unit.route_id;
                });
                this.markers[unit.route_id] = marker;
            }
            marker.bindPopup(this.unitPopup(unit));
        });

        // Retirar del mapa las rutas que ya no están activas.
        Object.keys(this.markers).forEach((routeId) => {
            if (!seen.has(parseInt(routeId, 10))) {
                this.map.removeLayer(this.markers[routeId]);
                delete this.markers[routeId];
            }
        });
    }

    unitPopup(unit) {
        const status = GPS_STATUS[unit.gps_status] || GPS_STATUS.offline;
        return `
            <div class="o_logistics_popup">
                <div class="o_logistics_popup_title">${escapeHtml(unit.driver_name)}</div>
                <div>${escapeHtml(unit.vehicle_name)} · ${escapeHtml(unit.vehicle_plate)}</div>
                <div><strong>Ruta:</strong> ${escapeHtml(unit.route_name)}</div>
                <div><strong>GPS:</strong> <span style="color:${status.color};">${status.label}</span></div>
                <div><strong>Velocidad:</strong> ${unit.speed} km/h</div>
                <div><strong>Avance:</strong> ${unit.completed_tasks} / ${unit.total_tasks} paradas</div>
                <div><strong>Siguiente:</strong> ${escapeHtml(unit.next_task_name) || "—"}</div>
            </div>`;
    }

    // ── Panel lateral ─────────────────────────────────────────────────────
    get visibleFleet() {
        const filter = this.state.filter;
        if (filter === "all") {
            return this.state.fleet;
        }
        if (filter === "deviated") {
            return this.state.fleet.filter((u) => u.deviated);
        }
        return this.state.fleet.filter((u) => u.gps_status === filter);
    }

    setFilter(filter) {
        this.state.filter = filter;
    }

    statusLabel(gpsStatus) {
        return (GPS_STATUS[gpsStatus] || GPS_STATUS.offline).label;
    }

    selectUnit(unit) {
        this.state.selectedRouteId = unit.route_id;
        if (!unit.latitude || !unit.longitude) {
            this.notification.add(
                `${unit.driver_name} aún no ha enviado su ubicación.`,
                { type: "warning" }
            );
            return;
        }
        this.map.setView([unit.latitude, unit.longitude], 16, { animate: true });
        const marker = this.markers[unit.route_id];
        if (marker) {
            marker.openPopup();
        }
    }

    openRoute(unit) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "logistics.route",
            res_id: unit.route_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    fitAll() {
        const markers = Object.values(this.markers);
        if (!markers.length) {
            this.map.setView(GUATEMALA_CITY, 11);
            return;
        }
        this.map.fitBounds(L.featureGroup(markers).getBounds().pad(0.2));
    }
}

registry.category("actions").add("logistics_control_tower", ControlTower);
