/**
 * gps_tracker.js — Rastreo GPS continuo desde el celular del piloto.
 * Envía la posición al servidor Odoo cada N segundos.
 * Soporta modo offline: guarda posiciones y sincroniza al reconectar.
 */

class LogisticsGpsTracker {
    constructor(options = {}) {
        this.driverId    = options.driverId || null;
        this.routeId     = options.routeId  || null;
        this.interval    = options.interval || 15; // segundos
        this.serverUrl   = options.serverUrl || "/logistics/gps/update";
        this.isTracking  = false;
        this.watchId     = null;
        this.sendTimer   = null;
        this.lastPosition = null;
        this.offlineQueue = this._loadOfflineQueue();
        this.onPositionUpdate = options.onPositionUpdate || null;
        this.onGeofenceTrigger = options.onGeofenceTrigger || null;
        this.onError = options.onError || null;
    }

    // ── Iniciar rastreo ───────────────────────────────────────────────────────
    start() {
        if (this.isTracking) return;
        if (!this.driverId) {
            console.error("GpsTracker: driverId requerido.");
            return;
        }
        if (!navigator.geolocation) {
            alert("Tu dispositivo no soporta GPS.");
            return;
        }
        this.isTracking = true;
        this._startWatchPosition();
        this._startSendTimer();
        this._syncOfflineQueue();
        console.log("🟢 GpsTracker iniciado para piloto ID:", this.driverId);
    }

    // ── Detener rastreo ───────────────────────────────────────────────────────
    stop() {
        this.isTracking = false;
        if (this.watchId !== null) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
        if (this.sendTimer) {
            clearInterval(this.sendTimer);
            this.sendTimer = null;
        }
        console.log("🔴 GpsTracker detenido.");
    }

    // ── Observar cambios de posición GPS ─────────────────────────────────────
    _startWatchPosition() {
        this.watchId = navigator.geolocation.watchPosition(
            (position) => this._onPositionReceived(position),
            (error)    => this._onGpsError(error),
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 5000,
            }
        );
    }

    _onPositionReceived(position) {
        const { latitude, longitude, speed, heading, accuracy } = position.coords;
        this.lastPosition = {
            driver_id: this.driverId,
            route_id:  this.routeId,
            latitude,
            longitude,
            speed:    speed    ? Math.round(speed * 3.6) : 0, // m/s → km/h
            heading:  heading  || 0,
            accuracy: accuracy || 0,
            timestamp: new Date().toISOString(),
        };
        // Notificar al UI
        if (this.onPositionUpdate) {
            this.onPositionUpdate(this.lastPosition);
        }
    }

    _onGpsError(error) {
        const messages = {
            1: "Permiso de ubicación denegado. Habilita el GPS en ajustes.",
            2: "No se pudo obtener la ubicación. Verifica la señal GPS.",
            3: "Tiempo de espera GPS agotado.",
        };
        const msg = messages[error.code] || "Error de GPS desconocido.";
        console.warn("GpsTracker error:", msg);
        if (this.onError) this.onError(msg);
    }

    // ── Enviar posición al servidor ───────────────────────────────────────────
    _startSendTimer() {
        this.sendTimer = setInterval(() => {
            this._sendPosition();
        }, this.interval * 1000);
    }

    async _sendPosition() {
        if (!this.lastPosition) return;
        const data = { ...this.lastPosition };

        // Si hay cola offline, intentar enviar primero
        await this._syncOfflineQueue();

        try {
            const response = await fetch(this.serverUrl, {
                method:  "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: data }),
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const result = await response.json();

            if (result.result?.geofence_triggered) {
                if (this.onGeofenceTrigger) {
                    this.onGeofenceTrigger(result.result.geofence_triggered);
                }
            }
        } catch (e) {
            // Sin conexión → guardar en cola offline
            console.warn("GpsTracker: Sin conexión, guardando offline:", e.message);
            this._addToOfflineQueue(data);
        }
    }

    // ── Cola offline (localStorage) ───────────────────────────────────────────
    _loadOfflineQueue() {
        try {
            return JSON.parse(localStorage.getItem("logistics_gps_queue") || "[]");
        } catch { return []; }
    }

    _saveOfflineQueue() {
        // Máximo 200 puntos en cola para no llenar el storage
        if (this.offlineQueue.length > 200) {
            this.offlineQueue = this.offlineQueue.slice(-200);
        }
        localStorage.setItem("logistics_gps_queue", JSON.stringify(this.offlineQueue));
    }

    _addToOfflineQueue(positionData) {
        this.offlineQueue.push(positionData);
        this._saveOfflineQueue();
    }

    async _syncOfflineQueue() {
        if (!this.offlineQueue.length) return;
        const queue = [...this.offlineQueue];
        for (const data of queue) {
            try {
                const response = await fetch(this.serverUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: data }),
                });
                if (response.ok) {
                    this.offlineQueue = this.offlineQueue.filter(
                        item => item.timestamp !== data.timestamp
                    );
                    this._saveOfflineQueue();
                }
            } catch { break; } // Sin conexión aún, detener
        }
    }

    // ── Obtener última posición conocida ──────────────────────────────────────
    getLastPosition() {
        return this.lastPosition;
    }

    // ── Verificar si hay conexión a internet ──────────────────────────────────
    isOnline() {
        return navigator.onLine;
    }
}

// Exportar para uso en driver_app.js
window.LogisticsGpsTracker = LogisticsGpsTracker;
