/**
 * driver_app.js — Lógica de la Progressive Web App para el piloto.
 * Interfaz simplificada y de fácil uso en celular.
 */

class DriverApp {
    constructor(config) {
        this.driverId      = config.driverId;
        this.routeId       = config.routeId;
        this.routeData     = config.routeData || {};
        this.apiKey        = config.apiKey || "";
        this.gpsInterval   = config.gpsInterval || 15;
        this.tasks         = this.routeData.tasks || [];
        this.currentTaskIndex = 0;
        this.gpsTracker    = null;
        this.preferredNav  = localStorage.getItem("preferred_nav_app") || "waze";
        this._init();
    }

    // ── Inicializar la app ────────────────────────────────────────────────────
    _init() {
        this._renderTaskList();
        this._bindEvents();
        this._updateProgressBar();
        this._startGpsTracking();
        this._checkOnlineStatus();
        // Registrar Service Worker para PWA
        if ("serviceWorker" in navigator) {
            navigator.serviceWorker.register("/logistics_route_manager/static/src/js/sw.js")
                .then(() => console.log("SW registrado"))
                .catch(e => console.warn("SW error:", e));
        }
    }

    // ── Renderizar lista de tareas ────────────────────────────────────────────
    _renderTaskList() {
        const container = document.getElementById("task-list");
        if (!container) return;
        container.innerHTML = "";

        this.tasks.forEach((task, index) => {
            const isActive = task.state === "in_transit";
            const isDone   = task.state === "completed";
            const isFailed = task.state === "failed";

            const el = document.createElement("div");
            el.className = `task-card ${isActive ? "active" : ""} ${isDone ? "done" : ""} ${isFailed ? "failed" : ""}`;
            el.dataset.taskId = task.id;
            el.dataset.index  = index;

            const typeIcon = { delivery: "📦", purchase: "🛒", errand: "📋", bank: "🏦" }[task.task_type] || "📍";
            const stateLabel = {
                pending: "Pendiente", in_transit: "En camino",
                arrived: "Llegué", completed: "✅ Completado", failed: "❌ Fallido",
            }[task.state] || task.state;

            const eta = task.estimated_arrival
                ? new Date(task.estimated_arrival).toLocaleTimeString("es-GT", { hour: "2-digit", minute: "2-digit" })
                : "--:--";

            el.innerHTML = `
                <div class="task-header">
                    <span class="task-number">${index + 1}</span>
                    <span class="task-type-icon">${typeIcon}</span>
                    <div class="task-info">
                        <div class="task-name">${task.name}</div>
                        <div class="task-address">📍 ${task.address || "Sin dirección"}</div>
                        ${task.contact_name ? `<div class="task-contact">👤 ${task.contact_name} ${task.contact_phone ? "· " + task.contact_phone : ""}</div>` : ""}
                    </div>
                    <div class="task-meta">
                        <div class="task-eta">🕐 ${eta}</div>
                        <div class="task-state-badge state-${task.state}">${stateLabel}</div>
                    </div>
                </div>
                ${isActive ? this._renderActiveTaskButtons(task) : ""}
            `;

            el.addEventListener("click", () => this._openTask(task, index));
            container.appendChild(el);
        });
    }

    _renderActiveTaskButtons(task) {
        return `
            <div class="active-task-actions">
                <div class="nav-buttons">
                    <button class="nav-btn waze-btn" onclick="driverApp.navigateWith('waze', ${task.latitude}, ${task.longitude}, '${task.name}'); event.stopPropagation();">
                        🚗 Navegar con Waze
                        ${this.preferredNav === "waze" ? '<span class="preferred-badge">⭐ Preferida</span>' : ""}
                    </button>
                    <button class="nav-btn gmaps-btn" onclick="driverApp.navigateWith('google_maps', ${task.latitude}, ${task.longitude}, '${task.name}'); event.stopPropagation();">
                        🗺️ Google Maps
                        ${this.preferredNav === "google_maps" ? '<span class="preferred-badge">⭐ Preferida</span>' : ""}
                    </button>
                </div>
                <div class="action-buttons">
                    <button class="action-btn arrived-btn" onclick="driverApp.markArrived(${task.id}); event.stopPropagation();">
                        📍 Llegué
                    </button>
                    <button class="action-btn complete-btn" onclick="driverApp.openCompleteModal(${task.id}); event.stopPropagation();">
                        ✅ Completar
                    </button>
                    <button class="action-btn fail-btn" onclick="driverApp.openFailModal(${task.id}); event.stopPropagation();">
                        ❌ Problema
                    </button>
                </div>
            </div>
        `;
    }

    // ── Navegación con Waze o Google Maps ─────────────────────────────────────
    navigateWith(app, lat, lng, name = "") {
        // Guardar preferencia
        localStorage.setItem("preferred_nav_app", app);
        this.preferredNav = app;

        const encodedName = encodeURIComponent(name);

        if (app === "waze") {
            // Deep link Waze — intenta app nativa, fallback a web
            const wazeNative = `waze://?ll=${lat},${lng}&navigate=yes&q=${encodedName}`;
            const wazeWeb    = `https://waze.com/ul?ll=${lat},${lng}&navigate=yes&q=${encodedName}`;
            window.location.href = wazeNative;
            setTimeout(() => window.open(wazeWeb, "_blank"), 1500);
        } else {
            // Deep link Google Maps — detecta Android/iOS
            const ua = navigator.userAgent.toLowerCase();
            if (/android/.test(ua)) {
                // Intent de Android para app nativa
                const intent = `intent://maps.google.com/maps?daddr=${lat},${lng}&mode=d#Intent;scheme=https;package=com.google.android.apps.maps;end`;
                window.location.href = intent;
            } else if (/iphone|ipad/.test(ua)) {
                // URL scheme iOS
                window.location.href = `comgooglemaps://?daddr=${lat},${lng}&directionsmode=driving`;
                setTimeout(() => {
                    window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving&dir_action=navigate`, "_blank");
                }, 1500);
            } else {
                window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving&dir_action=navigate`, "_blank");
            }
        }
    }

    // ── Marcar llegada ────────────────────────────────────────────────────────
    async markArrived(taskId) {
        try {
            const res = await fetch(`/logistics/task/${taskId}/arrived`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: {} }),
            });
            const data = await res.json();
            if (data.result?.success) {
                this._updateTaskState(taskId, "arrived");
                this._showToast("📍 Llegada registrada", "success");
            }
        } catch (e) {
            this._showToast("Sin conexión. Se guardará al reconectar.", "warning");
        }
    }

    // ── Modal para completar tarea ────────────────────────────────────────────
    openCompleteModal(taskId) {
        const modal = document.getElementById("complete-modal");
        if (modal) {
            modal.dataset.taskId = taskId;
            modal.style.display  = "flex";
        }
    }

    async completeTask(taskId) {
        const photoInput = document.getElementById("evidence-photo");
        const sigCanvas  = document.getElementById("signature-canvas");
        const sigName    = document.getElementById("signature-name");
        const spent      = document.getElementById("spent-amount");

        const params = {};
        if (photoInput?.files[0]) {
            params.evidence_photo_1 = await this._fileToBase64(photoInput.files[0]);
        }
        if (sigCanvas) {
            params.signature = sigCanvas.toDataURL("image/png").split(",")[1];
        }
        if (sigName?.value)  params.signature_name = sigName.value;
        if (spent?.value)    params.spent_amount   = parseFloat(spent.value);

        try {
            const res = await fetch(`/logistics/task/${taskId}/complete`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
            });
            const data = await res.json();
            if (data.result?.success) {
                this._updateTaskState(taskId, "completed");
                this._closeModal("complete-modal");
                this._showToast("✅ Tarea completada", "success");
                this._updateProgressBar();
                if (data.result.next_task_id) {
                    this._updateTaskState(data.result.next_task_id, "in_transit");
                    this._renderTaskList(); // Re-renderizar para mostrar botones en nueva tarea activa
                    setTimeout(() => {
                        document.querySelector(`.task-card.active`)?.scrollIntoView({ behavior: "smooth" });
                    }, 300);
                }
            }
        } catch (e) {
            this._showToast("Error al completar. Intenta de nuevo.", "danger");
        }
    }

    // ── Modal para reportar fallo ─────────────────────────────────────────────
    openFailModal(taskId) {
        const modal = document.getElementById("fail-modal");
        if (modal) {
            modal.dataset.taskId = taskId;
            modal.style.display  = "flex";
        }
    }

    async reportFail(taskId, reason) {
        try {
            const res = await fetch(`/logistics/task/${taskId}/fail`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: { reason } }),
            });
            const data = await res.json();
            if (data.result?.success) {
                this._updateTaskState(taskId, "failed");
                this._closeModal("fail-modal");
                this._showToast("❌ Problema reportado", "warning");
            }
        } catch (e) {
            this._showToast("Error. Intenta de nuevo.", "danger");
        }
    }

    // ── Iniciar rastreo GPS ───────────────────────────────────────────────────
    _startGpsTracking() {
        this.gpsTracker = new LogisticsGpsTracker({
            driverId: this.driverId,
            routeId:  this.routeId,
            interval: this.gpsInterval,
            onPositionUpdate: (pos) => {
                const speedEl = document.getElementById("driver-speed");
                if (speedEl) speedEl.textContent = `${pos.speed} km/h`;
            },
            onGeofenceTrigger: (data) => {
                this._showToast(`📍 Llegaste a: ${data.task_name}`, "info");
                this._updateTaskState(data.task_id, "arrived");
            },
            onError: (msg) => this._showToast(msg, "danger"),
        });
        if (this.routeData.state === "in_progress") {
            this.gpsTracker.start();
        }
    }

    // ── Barra de progreso ─────────────────────────────────────────────────────
    _updateProgressBar() {
        const total     = this.tasks.length;
        const completed = this.tasks.filter(t => t.state === "completed").length;
        const pct       = total ? Math.round(completed / total * 100) : 0;
        const bar       = document.getElementById("progress-bar");
        const label     = document.getElementById("progress-label");
        if (bar)   bar.style.width   = `${pct}%`;
        if (label) label.textContent = `${completed} / ${total} completadas (${pct}%)`;
    }

    // ── Estado online / offline ───────────────────────────────────────────────
    _checkOnlineStatus() {
        const updateBanner = () => {
            const banner = document.getElementById("offline-banner");
            if (banner) banner.style.display = navigator.onLine ? "none" : "flex";
        };
        window.addEventListener("online",  updateBanner);
        window.addEventListener("offline", updateBanner);
        updateBanner();
    }

    // ── Helpers ───────────────────────────────────────────────────────────────
    _updateTaskState(taskId, newState) {
        const task = this.tasks.find(t => t.id === taskId);
        if (task) task.state = newState;
        this._renderTaskList();
    }

    _closeModal(modalId) {
        const m = document.getElementById(modalId);
        if (m) m.style.display = "none";
    }

    _showToast(message, type = "info") {
        const container = document.getElementById("toast-container") || document.body;
        const toast = document.createElement("div");
        toast.className = `logistics-toast toast-${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.classList.add("show"), 50);
        setTimeout(() => { toast.classList.remove("show"); setTimeout(() => toast.remove(), 300); }, 3000);
    }

    async _fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload  = () => resolve(reader.result.split(",")[1]);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    _bindEvents() {
        document.getElementById("start-route-btn")?.addEventListener("click", () => {
            if (this.gpsTracker) this.gpsTracker.start();
        });
        document.getElementById("complete-modal-confirm")?.addEventListener("click", () => {
            const taskId = parseInt(document.getElementById("complete-modal")?.dataset.taskId);
            if (taskId) this.completeTask(taskId);
        });
        document.getElementById("fail-modal-confirm")?.addEventListener("click", () => {
            const modal  = document.getElementById("fail-modal");
            const taskId = parseInt(modal?.dataset.taskId);
            const reason = document.getElementById("fail-reason")?.value || "";
            if (taskId) this.reportFail(taskId, reason);
        });
        document.querySelectorAll(".close-modal").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".modal-overlay").forEach(m => m.style.display = "none");
            });
        });
    }

    _openTask(task, index) {
        // Solo expandir tarea activa al hacer click
        if (task.state === "pending" || task.state === "in_transit") {
            this.tasks.forEach(t => { if (t.id !== task.id && t.state === "in_transit") t.state = "pending"; });
            task.state = "in_transit";
            this._renderTaskList();
        }
    }
}

// Inicialización global de la app del piloto
window.initDriverApp = function(config) {
    window.driverApp = new DriverApp(config);
};
