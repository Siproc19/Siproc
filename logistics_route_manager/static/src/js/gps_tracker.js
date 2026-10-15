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
        this.token       = options.token || "";
        this.isTracking  = false;
        this.watchId     = null;
        this.sendTimer   = null;
        this.lastPosition = null;
        this.offlineQueue = this._loadOfflineQueue();
        this.onPositionUpdate = options.onPositionUpdate || null;
        this.onGeofenceTrigger = options.onGeofenceTrigger || null;
        this.onError = options.onError || null;
        // Avisos de lo que pasa con cada envío al servidor.
        this.onSent = options.onSent || null;
        this.onSendError = options.onSendError || null;

        // ── Vida de la pantalla ──────────────────────────────────────────
        // Cuando el piloto se pasa a Waze, el teléfono congela esta página:
        // el navegador deja de correr nuestro código. No hay forma de
        // evitarlo desde una app web. Lo que sí se puede es:
        //   * mandar la última posición JUSTO ANTES de irse,
        //   * y mandar una nueva EN CUANTO vuelve.
        // Así la Torre nunca ve el hueco completo.
        this.wakeLock = null;
        this._alCambiarVisibilidad = () => this._manejarVisibilidad();
        this._alEsconderse = () => this._mandarUltimaSeñalDeSalida();
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
        document.addEventListener("visibilitychange", this._alCambiarVisibilidad);
        // `pagehide` es el único aviso confiable en iOS; en Android llega
        // `visibilitychange`. Se escuchan los dos y el envío se protege
        // contra repetirse.
        window.addEventListener("pagehide", this._alEsconderse);
        this._pedirWakeLock();
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
        document.removeEventListener("visibilitychange", this._alCambiarVisibilidad);
        window.removeEventListener("pagehide", this._alEsconderse);
        this._soltarWakeLock();
        console.log("🔴 GpsTracker detenido.");
    }

    // ── Que la pantalla no se apague sola ────────────────────────────────────
    async _pedirWakeLock() {
        // Con la pantalla apagada el navegador también congela la página.
        // El Wake Lock la mantiene encendida mientras la app está al frente.
        // No todos los teléfonos lo tienen; si falta, no pasa nada.
        if (!("wakeLock" in navigator)) return;
        try {
            this.wakeLock = await navigator.wakeLock.request("screen");
            this.wakeLock.addEventListener("release", () => {
                this.wakeLock = null;
            });
        } catch (e) {
            console.warn("GpsTracker: no se pudo mantener la pantalla encendida:", e.message);
        }
    }

    _soltarWakeLock() {
        if (this.wakeLock) {
            try { this.wakeLock.release(); } catch { /* ya se soltó */ }
            this.wakeLock = null;
        }
    }

    // ── Irse a Waze y volver ────────────────────────────────────────────────
    _manejarVisibilidad() {
        if (!this.isTracking) return;
        if (document.visibilityState === "hidden") {
            this._mandarUltimaSeñalDeSalida();
            return;
        }
        // Volvió. El sistema operativo nos devolvió el control: se pide una
        // posición fresca de inmediato en vez de esperar al próximo ciclo,
        // y se vacía lo que quedó guardado en el teléfono.
        this._pedirWakeLock();
        this._posicionInmediata();
        this._syncOfflineQueue();
    }

    _posicionInmediata() {
        if (!navigator.geolocation) return;
        navigator.geolocation.getCurrentPosition(
            (position) => {
                this._onPositionReceived(position);
                this._sendPosition();
            },
            () => this._sendPosition(),   // sin lectura nueva, manda la última
            { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
        );
    }

    /**
     * Manda la última posición justo antes de que el teléfono nos congele.
     *
     * `fetch` normal no sirve aquí: el navegador puede matarlo a medias al
     * cambiar de app. `sendBeacon` está hecho exactamente para esto — el
     * sistema se encarga de entregarlo aunque la página ya se haya ido.
     */
    _mandarUltimaSeñalDeSalida() {
        if (!this.lastPosition || !this.token) return;
        if (!navigator.sendBeacon) return;

        // No repetir el mismo punto si `pagehide` y `visibilitychange`
        // llegan los dos.
        if (this._ultimoBeacon === this.lastPosition.timestamp) return;
        this._ultimoBeacon = this.lastPosition.timestamp;

        const p = this.lastPosition;
        const datos = new URLSearchParams({
            token: this.token,
            lat: p.latitude,
            lon: p.longitude,
            // El endpoint de rastreador recibe metros por segundo.
            speed: (p.speed || 0) / 3.6,
            heading: p.heading || 0,
            acc: p.accuracy || 0,
        });
        try {
            navigator.sendBeacon(
                "/logistics/gps/push",
                new Blob([datos.toString()],
                         { type: "application/x-www-form-urlencoded" })
            );
        } catch (e) {
            console.warn("GpsTracker: no se pudo mandar la señal de salida:", e.message);
        }
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
        const data = { ...this.lastPosition, token: this.token };

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

            // El servidor puede responder 200 y aun así rechazar el dato.
            // Antes eso se daba por bueno y la posición se perdía en
            // silencio: por fuera parecía que el GPS estaba enviando.
            if (result.result?.success === false) {
                const motivo = result.result.error || "el servidor rechazó la posición";
                console.warn("GpsTracker: rechazado por el servidor:", motivo);
                this._addToOfflineQueue(data);
                if (this.onSendError) this.onSendError(motivo);
                return;
            }
            if (result.error) {
                const motivo = result.error.message || "error del servidor";
                this._addToOfflineQueue(data);
                if (this.onSendError) this.onSendError(motivo);
                return;
            }

            if (this.onSent) this.onSent(data);

            if (result.result?.geofence_triggered) {
                if (this.onGeofenceTrigger) {
                    this.onGeofenceTrigger(result.result.geofence_triggered);
                }
            }
        } catch (e) {
            // Sin conexión → guardar en cola offline
            console.warn("GpsTracker: Sin conexión, guardando offline:", e.message);
            this._addToOfflineQueue(data);
            if (this.onSendError) this.onSendError("sin conexión, guardado en el teléfono");
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
