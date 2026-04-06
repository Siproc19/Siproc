/** @odoo-module **/

const LogisticsRouteMap = {
    state: {
        map: null,
        driverMarker: null,
        taskMarkers: [],
        routePolyline: null,
        trafficLayer: null,
        routeData: null,
        initializedFor: null,
        pollTimer: null,
    },

    async init() {
        const mapEl = document.getElementById("logistics_route_map");
        if (!mapEl) {
            return;
        }
        const routeId = this._getRouteId(mapEl);
        if (!routeId) {
            mapEl.innerHTML = '<div style="padding:24px;color:#6c757d;">Guarda la ruta para poder mostrar el mapa.</div>';
            return;
        }
        if (this.state.initializedFor === routeId) {
            return;
        }
        this.state.initializedFor = routeId;
        this._clearPolling();
        mapEl.innerHTML = '<div style="padding:24px;color:#6c757d;">Cargando mapa...</div>';

        const config = await this._fetchJson('/logistics/config').catch(() => ({ success: false }));
        const apiKey = config && config.success ? (config.google_maps_api_key || '') : '';
        if (apiKey) {
            await this._ensureGoogleMaps(apiKey);
            this._initGoogleMap(mapEl);
        } else {
            this._renderOsmFallback(mapEl, null);
        }
        await this.refresh();
        this.state.pollTimer = window.setInterval(() => this.refresh(), 15000);
        this._bindControls();
    },

    _getRouteId(mapEl) {
        const fromData = parseInt(mapEl.dataset.routeId || '', 10);
        if (fromData) return fromData;
        const hash = window.location.hash || '';
        const match = hash.match(/[?&]id=(\d+)/);
        if (match) return parseInt(match[1], 10);
        return null;
    },

    async _fetchJson(url, options = {}) {
        const response = await fetch(url, {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' },
            ...options,
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    },

    async _ensureGoogleMaps(apiKey) {
        if (window.google && window.google.maps) return;
        await new Promise((resolve, reject) => {
            const existing = document.querySelector('script[data-logistics-google="1"]');
            if (existing) {
                existing.addEventListener('load', resolve, { once: true });
                existing.addEventListener('error', reject, { once: true });
                return;
            }
            const script = document.createElement('script');
            script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=geometry`;
            script.async = true;
            script.defer = true;
            script.dataset.logisticsGoogle = '1';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    },

    _initGoogleMap(mapEl) {
        if (this.state.map || !(window.google && window.google.maps)) return;
        this.state.map = new google.maps.Map(mapEl, {
            center: { lat: 14.6349, lng: -90.5069 },
            zoom: 12,
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: true,
        });
        this.state.trafficLayer = new google.maps.TrafficLayer();
    },

    _renderOsmFallback(mapEl, center) {
        const lat = center && center.lat ? center.lat : 14.6349;
        const lng = center && center.lng ? center.lng : -90.5069;
        const delta = 0.03;
        const src = `https://www.openstreetmap.org/export/embed.html?bbox=${lng-delta}%2C${lat-delta}%2C${lng+delta}%2C${lat+delta}&layer=mapnik&marker=${lat}%2C${lng}`;
        mapEl.innerHTML = `<iframe title="Mapa" src="${src}" style="width:100%;height:100%;border:0;border-radius:12px;"></iframe>`;
    },

    async refresh() {
        const mapEl = document.getElementById("logistics_route_map");
        if (!mapEl) return;
        const routeId = this._getRouteId(mapEl);
        if (!routeId) return;
        try {
            const payload = await this._fetchJson(`/logistics/route/${routeId}/status`);
            if (!payload.success) throw new Error(payload.error || 'No se pudo cargar la ruta');
            this.state.routeData = payload.data;
            this._render(payload.data, mapEl);
        } catch (err) {
            console.error('LogisticsRouteMap refresh error', err);
            mapEl.innerHTML = `<div style="padding:24px;color:#dc3545;">No se pudo cargar el mapa: ${err.message}</div>`;
        }
    },

    _render(data, mapEl) {
        const driver = data.driver || {};
        const taskPoints = (data.tasks || []).filter(t => t.latitude && t.longitude);
        const firstPoint = taskPoints[0];
        const center = driver.latitude && driver.longitude
            ? { lat: driver.latitude, lng: driver.longitude }
            : firstPoint
                ? { lat: firstPoint.latitude, lng: firstPoint.longitude }
                : { lat: 14.6349, lng: -90.5069 };

        if (!(window.google && window.google.maps) || !this.state.map) {
            this._renderOsmFallback(mapEl, center);
            return;
        }

        this.state.taskMarkers.forEach(marker => marker.setMap(null));
        this.state.taskMarkers = [];
        if (this.state.driverMarker) this.state.driverMarker.setMap(null);
        if (this.state.routePolyline) this.state.routePolyline.setMap(null);

        const bounds = new google.maps.LatLngBounds();
        taskPoints.forEach((task, index) => {
            const pos = { lat: task.latitude, lng: task.longitude };
            const marker = new google.maps.Marker({
                position: pos,
                map: this.state.map,
                title: task.name || `Parada ${index + 1}`,
                label: `${index + 1}`,
            });
            const info = new google.maps.InfoWindow({
                content: `<div style="max-width:220px;"><strong>${task.name || 'Parada'}</strong><br/>${task.address || ''}<br/><small>Estado: ${task.state || ''}</small></div>`,
            });
            marker.addListener('click', () => info.open(this.state.map, marker));
            this.state.taskMarkers.push(marker);
            bounds.extend(pos);
        });

        if (driver.latitude && driver.longitude) {
            this.state.driverMarker = new google.maps.Marker({
                position: { lat: driver.latitude, lng: driver.longitude },
                map: this.state.map,
                title: driver.name || 'Piloto',
                icon: 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png',
            });
            bounds.extend({ lat: driver.latitude, lng: driver.longitude });
        }

        if (Array.isArray(data.polyline) && data.polyline.length > 1) {
            this.state.routePolyline = new google.maps.Polyline({
                path: data.polyline.map(p => ({ lat: p.lat || p.latitude, lng: p.lng || p.longitude })),
                geodesic: true,
                strokeColor: '#0d6efd',
                strokeOpacity: 0.8,
                strokeWeight: 4,
            });
            this.state.routePolyline.setMap(this.state.map);
        }

        if (taskPoints.length || (driver.latitude && driver.longitude)) {
            this.state.map.fitBounds(bounds);
            const listener = google.maps.event.addListenerOnce(this.state.map, 'idle', () => {
                if (this.state.map.getZoom() > 15) this.state.map.setZoom(15);
                google.maps.event.removeListener(listener);
            });
        } else {
            this.state.map.setCenter(center);
        }
    },

    _bindControls() {
        const centerBtn = document.getElementById('btn_center_driver');
        if (centerBtn && !centerBtn.dataset.bound) {
            centerBtn.dataset.bound = '1';
            centerBtn.addEventListener('click', () => {
                const driver = this.state.routeData && this.state.routeData.driver;
                if (driver && driver.latitude && driver.longitude && this.state.map) {
                    this.state.map.panTo({ lat: driver.latitude, lng: driver.longitude });
                    this.state.map.setZoom(15);
                }
            });
        }
        const trafficBtn = document.getElementById('btn_show_traffic');
        if (trafficBtn && !trafficBtn.dataset.bound) {
            trafficBtn.dataset.bound = '1';
            trafficBtn.addEventListener('click', () => {
                if (!this.state.trafficLayer || !this.state.map) return;
                const visible = this.state.trafficLayer.getMap();
                this.state.trafficLayer.setMap(visible ? null : this.state.map);
            });
        }
        const routeBtn = document.getElementById('btn_show_route');
        if (routeBtn && !routeBtn.dataset.bound) {
            routeBtn.dataset.bound = '1';
            routeBtn.addEventListener('click', () => this.refresh());
        }
        const wazeBtn = document.getElementById('btn_open_waze');
        if (wazeBtn && !wazeBtn.dataset.bound) {
            wazeBtn.dataset.bound = '1';
            wazeBtn.addEventListener('click', () => {
                const next = (this.state.routeData?.tasks || []).find(t => ['pending','in_transit','arrived'].includes(t.state) && t.latitude && t.longitude);
                if (next) window.open(`https://waze.com/ul?ll=${next.latitude},${next.longitude}&navigate=yes`, '_blank');
            });
        }
        const gmapsBtn = document.getElementById('btn_open_gmaps');
        if (gmapsBtn && !gmapsBtn.dataset.bound) {
            gmapsBtn.dataset.bound = '1';
            gmapsBtn.addEventListener('click', () => {
                const next = (this.state.routeData?.tasks || []).find(t => ['pending','in_transit','arrived'].includes(t.state) && t.latitude && t.longitude);
                if (next) window.open(`https://www.google.com/maps/dir/?api=1&destination=${next.latitude},${next.longitude}&travelmode=driving`, '_blank');
            });
        }
    },

    _clearPolling() {
        if (this.state.pollTimer) {
            window.clearInterval(this.state.pollTimer);
            this.state.pollTimer = null;
        }
    },
};

function tryInitLogisticsMap() {
    const mapEl = document.getElementById('logistics_route_map');
    if (mapEl) {
        LogisticsRouteMap.init();
    }
}

document.addEventListener('DOMContentLoaded', tryInitLogisticsMap);
window.addEventListener('hashchange', () => window.setTimeout(tryInitLogisticsMap, 300));
const observer = new MutationObserver(() => {
    if (document.getElementById('logistics_route_map')) {
        tryInitLogisticsMap();
    }
});
observer.observe(document.body, { childList: true, subtree: true });
