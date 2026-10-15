/** @odoo-module **/

/**
 * Mapa de una ruta — Leaflet + OpenStreetMap (sin API Key).
 *
 * Se usa dentro del formulario de la ruta como:
 *     <widget name="logistics_route_map"/>
 *
 * Muestra la posición actual del piloto (enviada desde su celular), el
 * recorrido real recorrido, y las paradas de la ruta.
 */

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import {
    TASK_COLORS,
    closedIcon,
    decodePolyline,
    driverIcon,
    metrosEntre,
    stopIcon,
    ensureLeaflet,
    escapeHtml,
    OSM_URL,
    OSM_ATTRIBUTION,
} from "./logistics_map_core";

const REFRESH_MS = 15000;

export class LogisticsRouteMapWidget extends Component {
    static template = "logistics_route_manager.RouteMapWidget";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.mapRef = useRef("map");

        this.state = useState({
            loading: true,
            error: "",
            followDriver: true,
            showTrack: true,
            driverOnline: false,
            driverSpeed: 0,
            deviated: false,
            deviationMessage: "",
            progress: 0,
            completedTasks: 0,
            totalTasks: 0,
            // Paradas que no se pueden pintar porque nadie les puso
            // ubicación. Antes se descartaban en silencio y el mapa salía
            // vacío sin explicar por qué.
            sinUbicacion: [],
        });

        // Objetos Leaflet — fuera de `state`, no deben provocar re-render.
        this.map = null;
        this.driverMarker = null;
        this.stopMarkers = [];
        this.closedMarkers = [];
        this.closedLines = [];
        this.trackLine = null;
        this.plannedLine = null;
        this.timer = null;
        this.lastDriverLatLng = null;

        onMounted(() => this.initMap());
        onWillUnmount(() => this.teardown());
    }

    get resId() {
        return this.props.record && this.props.record.resId;
    }

    async initMap() {
        if (!ensureLeaflet(this.state)) {
            return;
        }
        if (!this.resId) {
            this.state.loading = false;
            this.state.error = "Guarda la ruta para poder ver el mapa.";
            return;
        }

        this.map = L.map(this.mapRef.el, {
            zoomControl: true,
            attributionControl: true,
        }).setView([14.6349, -90.5069], 12); // Ciudad de Guatemala por defecto

        L.tileLayer(OSM_URL, {
            maxZoom: 19,
            attribution: OSM_ATTRIBUTION,
        }).addTo(this.map);

        // Leaflet mide el contenedor al crearse. Dentro de un formulario de
        // Odoo el layout aún no está estabilizado, así que se recalcula.
        setTimeout(() => this.map && this.map.invalidateSize(), 250);

        await this.refresh(true);
        this.timer = setInterval(() => this.refresh(false), REFRESH_MS);
    }

    teardown() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
        if (this.map) {
            this.map.remove();
            this.map = null;
        }
    }

    async refresh(fitBounds) {
        if (!this.map || !this.resId) {
            return;
        }
        let data;
        try {
            data = await this.orm.call(
                "logistics.route",
                "get_route_map_data",
                [[this.resId]]
            );
        } catch (error) {
            this.state.error = "No se pudo cargar el mapa de la ruta.";
            this.state.loading = false;
            return;
        }

        this.state.loading = false;
        this.state.error = "";
        this.state.deviated = data.deviated;
        this.state.deviationMessage = data.deviation_message || "";
        this.state.progress = Math.round(data.progress || 0);
        this.state.completedTasks = data.completed_tasks || 0;
        this.state.totalTasks = data.total_tasks || 0;
        this.state.driverOnline = !!(data.driver && data.driver.is_online);
        this.state.driverSpeed = data.driver ? Math.round(data.driver.speed || 0) : 0;

        this.drawStops(data.tasks || []);
        this.drawTrack(data.gps_track || []);
        this.drawPlanned(data.polyline);
        this.drawDriver(data.driver);

        if (fitBounds) {
            this.fitAll();
        } else if (this.state.followDriver && this.lastDriverLatLng) {
            this.map.panTo(this.lastDriverLatLng, { animate: true });
        }
    }

    drawStops(tasks) {
        this.stopMarkers.forEach((m) => this.map.removeLayer(m));
        this.closedMarkers.forEach((m) => this.map.removeLayer(m));
        this.closedLines.forEach((l) => this.map.removeLayer(l));
        this.stopMarkers = [];
        this.closedMarkers = [];
        this.closedLines = [];

        const ordenadas = [...tasks].sort((a, b) => a.sequence - b.sequence);

        // El número de la parada es su lugar en la ruta, se pinte o no. Antes
        // se numeraba sobre la lista ya filtrada, así que una parada sin
        // coordenadas corría la numeración de todas las demás y el mapa no
        // cuadraba con la lista de la ruta.
        this.state.sinUbicacion = ordenadas
            .filter((t) => !(t.latitude && t.longitude))
            .map((t, i) => ({ nombre: t.name, posicion: ordenadas.indexOf(t) + 1 }));

        ordenadas.forEach((task, index) => {
            const numero = index + 1;
            if (task.latitude && task.longitude) {
                const color = TASK_COLORS[task.state] || TASK_COLORS.pending;
                const marker = L.marker([task.latitude, task.longitude], {
                    icon: stopIcon(numero, color),
                    title: task.name,
                }).addTo(this.map);
                marker.bindPopup(this.stopPopup(task, numero));
                this.stopMarkers.push(marker);
            }
            this.drawClosedPoint(task, numero);
        });
    }

    /**
     * Pinta dónde el piloto cerró la parada, cuando ese punto es distinto
     * del planificado. Así queda constancia visible en el mapa de que ahí
     * hubo una entrega — que era justo lo que faltaba al darle Completar.
     */
    drawClosedPoint(task, numero) {
        if (!["completed", "failed"].includes(task.state)) {
            return;
        }
        const lat = task.closed_latitude;
        const lng = task.closed_longitude;
        if (!lat || !lng) {
            return;
        }
        const entregada = task.state === "completed";

        let distancia = null;
        if (task.latitude && task.longitude) {
            distancia = metrosEntre(task.latitude, task.longitude, lat, lng);
            // A menos de 30 m es el mismo lugar; dos marcadores encimados
            // solo estorban.
            if (distancia < 30) {
                return;
            }
            const linea = L.polyline(
                [[task.latitude, task.longitude], [lat, lng]],
                { color: entregada ? TASK_COLORS.completed : TASK_COLORS.failed,
                  weight: 2, opacity: 0.6, dashArray: "4, 6" }
            ).addTo(this.map);
            this.closedLines.push(linea);
        }

        const marker = L.marker([lat, lng], {
            icon: closedIcon(entregada),
            title: `${numero}. ${task.name}`,
            zIndexOffset: 500,
        }).addTo(this.map);
        marker.bindPopup(this.closedPopup(task, numero, distancia));
        this.closedMarkers.push(marker);
    }

    horaDe(iso) {
        if (!iso) {
            return "—";
        }
        return new Date(iso + "Z").toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    closedPopup(task, numero, distancia) {
        const entregada = task.state === "completed";
        const partes = [
            `<div class="o_logistics_popup_title">${entregada ? "✓ Entregado aquí" : "✕ No se pudo entregar"}</div>`,
            `<div>${numero}. ${escapeHtml(task.name)}</div>`,
            `<div><strong>Hora:</strong> ${this.horaDe(task.actual_departure)}</div>`,
        ];
        if (entregada && task.signature_name) {
            partes.push(`<div><strong>Recibió:</strong> ${escapeHtml(task.signature_name)}</div>`);
        }
        if (!entregada && task.failure_reason) {
            partes.push(`<div><strong>Motivo:</strong> ${escapeHtml(task.failure_reason)}</div>`);
        }
        if (distancia !== null) {
            partes.push(
                `<div><strong>Del punto planificado:</strong> ${distancia} m</div>`
            );
        }
        return `<div class="o_logistics_popup">${partes.join("")}</div>`;
    }

    stopPopup(task, position) {
        const escape = escapeHtml;
        const eta = task.estimated_arrival
            ? new Date(task.estimated_arrival + "Z").toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
              })
            : "—";
        const prestada = task.coord_source && task.coord_source !== "parada"
            ? `<div class="text-muted">Ubicación tomada ${
                  task.coord_source === "cliente"
                      ? "de la ficha del cliente"
                      : "de la entrega anterior"
              }</div>`
            : "";
        return `
            <div class="o_logistics_popup">
                <div class="o_logistics_popup_title">${position}. ${escape(task.name)}</div>
                <div>${escape(task.address)}</div>
                ${prestada}
                <div><strong>Contacto:</strong> ${escape(task.contact_name) || "—"}
                     ${task.contact_phone ? " · " + escape(task.contact_phone) : ""}</div>
                <div><strong>Llegada estimada:</strong> ${eta}</div>
                <div class="o_logistics_popup_nav">
                    <a href="https://waze.com/ul?ll=${task.latitude},${task.longitude}&amp;navigate=yes"
                       target="_blank" rel="noopener">Waze</a>
                    <a href="https://www.google.com/maps?q=${task.latitude},${task.longitude}"
                       target="_blank" rel="noopener">Google Maps</a>
                </div>
            </div>`;
    }

    drawTrack(track) {
        if (this.trackLine) {
            this.map.removeLayer(this.trackLine);
            this.trackLine = null;
        }
        if (!this.state.showTrack || track.length < 2) {
            return;
        }
        this.trackLine = L.polyline(track, {
            color: "#3d4c1e",
            weight: 4,
            opacity: 0.75,
        }).addTo(this.map);
    }

    drawPlanned(polyline) {
        if (this.plannedLine) {
            this.map.removeLayer(this.plannedLine);
            this.plannedLine = null;
        }
        if (!polyline || !polyline.polyline) {
            return;
        }
        const points = decodePolyline(polyline.polyline);
        if (points.length < 2) {
            return;
        }
        this.plannedLine = L.polyline(points, {
            color: "#6c757d",
            weight: 3,
            opacity: 0.55,
            dashArray: "8, 8",
        }).addTo(this.map);
    }

    drawDriver(driver) {
        if (!driver || !driver.latitude || !driver.longitude) {
            return;
        }
        const latlng = [driver.latitude, driver.longitude];
        this.lastDriverLatLng = latlng;

        if (this.driverMarker) {
            this.driverMarker.setLatLng(latlng);
            this.driverMarker.setIcon(driverIcon(driver.is_online));
        } else {
            this.driverMarker = L.marker(latlng, {
                icon: driverIcon(driver.is_online),
                zIndexOffset: 1000,
            }).addTo(this.map);
        }
        this.driverMarker.bindPopup(
            `<div class="o_logistics_popup">
                <div class="o_logistics_popup_title">${escapeHtml(driver.name)}</div>
                <div>${driver.is_online ? "En línea" : "Sin señal reciente"}</div>
                <div><strong>Velocidad:</strong> ${Math.round(driver.speed || 0)} km/h</div>
             </div>`
        );
    }

    // ── Acciones de la barra ──────────────────────────────────────────────
    fitAll() {
        const layers = [...this.stopMarkers, ...this.closedMarkers];
        if (this.driverMarker) {
            layers.push(this.driverMarker);
        }
        if (!layers.length) {
            return;
        }
        const group = L.featureGroup(layers);
        this.map.fitBounds(group.getBounds().pad(0.15));
    }

    centerOnDriver() {
        if (!this.lastDriverLatLng) {
            this.notification.add("El piloto aún no ha enviado su ubicación.", {
                type: "warning",
            });
            return;
        }
        this.map.setView(this.lastDriverLatLng, 16, { animate: true });
    }

    toggleFollow() {
        this.state.followDriver = !this.state.followDriver;
    }

    toggleTrack() {
        this.state.showTrack = !this.state.showTrack;
        this.refresh(false);
    }

    openIn(app) {
        if (!this.lastDriverLatLng) {
            this.notification.add("El piloto aún no ha enviado su ubicación.", {
                type: "warning",
            });
            return;
        }
        const [lat, lng] = this.lastDriverLatLng;
        const url =
            app === "waze"
                ? `https://waze.com/ul?ll=${lat},${lng}&navigate=yes`
                : `https://www.google.com/maps?q=${lat},${lng}`;
        window.open(url, "_blank", "noopener");
    }
}

registry.category("view_widgets").add("logistics_route_map", {
    component: LogisticsRouteMapWidget,
});
