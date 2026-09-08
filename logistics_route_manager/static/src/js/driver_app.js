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
            // Primero limpiar lo de la parada anterior, y solo después medir
            // el canvas: con el modal oculto su ancho es 0 y no se puede firmar.
            this._limpiarModalCompletar();
            this._prepararFirma();
            this._ligarFoto();
        }
    }

    async completeTask(taskId) {
        const photoInput = document.getElementById("evidence-photo");
        const sigCanvas  = document.getElementById("signature-canvas");
        const sigName    = document.getElementById("signature-name");
        const spent      = document.getElementById("spent-amount");

        const boton = document.getElementById("complete-modal-confirm");
        const params = {};

        // La foto ya viene reducida desde que se eligió. Si por lo que sea no
        // se pudo reducir, se manda tal cual.
        if (this._fotoLista) {
            params.evidence_photo_1 = this._fotoLista;
        } else if (photoInput?.files[0]) {
            params.evidence_photo_1 = await this._fileToBase64(photoInput.files[0]);
        }
        // Solo se manda la firma si de verdad se trazó algo: antes se enviaba
        // siempre un recuadro en blanco.
        if (sigCanvas && this._firmaTrazada) {
            params.signature = sigCanvas.toDataURL("image/png").split(",")[1];
        }
        if (sigName?.value)  params.signature_name = sigName.value.trim();
        if (spent?.value)    params.spent_amount   = parseFloat(spent.value);

        if (boton) { boton.disabled = true; boton.textContent = "Guardando…"; }

        const restaurar = () => {
            if (boton) { boton.disabled = false; boton.textContent = "✅ Confirmar Completado"; }
        };

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
            } else {
                restaurar();
                this._showToast(
                    data.result?.error || "No se pudo guardar. Inténtelo de nuevo.",
                    "danger"
                );
            }
        } catch (e) {
            restaurar();
            this._showToast("No se pudo guardar. Revise la señal e inténtelo de nuevo.", "danger");
        }
    }

    // ── Modal de completar: limpieza, firma y foto ────────────────────────────

    _limpiarModalCompletar() {
        // Sin esto, la foto y la firma de la parada anterior se quedaban
        // cargadas y se volvían a mandar en la siguiente entrega.
        const foto = document.getElementById("evidence-photo");
        if (foto) foto.value = "";
        const vista = document.getElementById("evidence-preview");
        if (vista) { vista.removeAttribute("src"); vista.style.display = "none"; }
        ["signature-name", "spent-amount"].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.value = "";
        });
        this._fotoLista = null;
        const boton = document.getElementById("complete-modal-confirm");
        if (boton) { boton.disabled = false; boton.textContent = "✅ Confirmar Completado"; }
    }

    _prepararFirma() {
        const c = document.getElementById("signature-canvas");
        if (!c) return;

        // El ancho se mide AHORA, con el modal ya en pantalla. Medirlo mientras
        // estaba oculto devolvía 0, el canvas quedaba de cero píxeles y el dedo
        // no pintaba nada: por eso no se podía firmar.
        const ancho = Math.round(c.getBoundingClientRect().width) || 300;
        c.width  = ancho;
        c.height = 150;

        const ctx = c.getContext("2d");
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, c.width, c.height);
        ctx.lineWidth   = 2.5;
        ctx.lineCap     = "round";
        ctx.lineJoin    = "round";
        ctx.strokeStyle = "#111111";
        this._firmaTrazada = false;

        if (c.dataset.ligado) return;
        c.dataset.ligado = "1";

        let trazando = false;
        const punto = (e) => {
            const r = c.getBoundingClientRect();
            const t = e.touches && e.touches[0] ? e.touches[0] : e;
            return { x: t.clientX - r.left, y: t.clientY - r.top };
        };
        const empezar = (e) => {
            e.preventDefault();
            trazando = true;
            const p = punto(e);
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            // Un toque suelto también deja marca.
            ctx.lineTo(p.x + 0.1, p.y);
            ctx.stroke();
            this._firmaTrazada = true;
        };
        const seguir = (e) => {
            if (!trazando) return;
            e.preventDefault();
            const p = punto(e);
            ctx.lineTo(p.x, p.y);
            ctx.stroke();
            this._firmaTrazada = true;
        };
        const soltar = () => { trazando = false; };

        c.addEventListener("touchstart", empezar, { passive: false });
        c.addEventListener("touchmove",  seguir,  { passive: false });
        c.addEventListener("touchend",   soltar);
        c.addEventListener("touchcancel", soltar);
        c.addEventListener("mousedown",  empezar);
        c.addEventListener("mousemove",  seguir);
        c.addEventListener("mouseup",    soltar);
        c.addEventListener("mouseleave", soltar);

        document.getElementById("clear-signature")?.addEventListener("click", () => {
            ctx.fillStyle = "#ffffff";
            ctx.fillRect(0, 0, c.width, c.height);
            ctx.strokeStyle = "#111111";
            this._firmaTrazada = false;
        });
    }

    _ligarFoto() {
        const input = document.getElementById("evidence-photo");
        if (!input || input.dataset.ligado) return;
        input.dataset.ligado = "1";
        input.addEventListener("change", async () => {
            const archivo = input.files && input.files[0];
            if (!archivo) return;
            this._showToast("Preparando la foto…", "info");
            try {
                this._fotoLista = await this._reducirImagen(archivo, 1280, 0.72);
                const vista = document.getElementById("evidence-preview");
                if (vista) {
                    vista.src = "data:image/jpeg;base64," + this._fotoLista;
                    vista.style.display = "block";
                }
                this._showToast("📷 Foto lista", "success");
            } catch (e) {
                this._fotoLista = null;
                this._showToast("No se pudo leer la foto. Tómela de nuevo.", "danger");
            }
        });
    }

    // Las fotos de un celular pesan varios megas. Enviarlas enteras por datos
    // móviles es lento y a veces el servidor rechaza el envío por tamaño.
    _reducirImagen(archivo, ladoMax, calidad) {
        return new Promise((resolver, rechazar) => {
            const lector = new FileReader();
            lector.onerror = () => rechazar(new Error("no se pudo leer el archivo"));
            lector.onload = () => {
                const img = new Image();
                img.onerror = () => rechazar(new Error("no se pudo decodificar la imagen"));
                img.onload = () => {
                    try {
                        const escala = Math.min(1, ladoMax / Math.max(img.width, img.height));
                        const lienzo = document.createElement("canvas");
                        lienzo.width  = Math.max(1, Math.round(img.width  * escala));
                        lienzo.height = Math.max(1, Math.round(img.height * escala));
                        const ctx = lienzo.getContext("2d");
                        ctx.fillStyle = "#ffffff";
                        ctx.fillRect(0, 0, lienzo.width, lienzo.height);
                        ctx.drawImage(img, 0, 0, lienzo.width, lienzo.height);
                        resolver(lienzo.toDataURL("image/jpeg", calidad).split(",")[1]);
                    } catch (err) {
                        rechazar(err);
                    }
                };
                img.src = lector.result;
            };
            lector.readAsDataURL(archivo);
        });
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
        document.getElementById("start-route-btn")?.addEventListener("click", async (ev) => {
            const boton = ev.currentTarget;
            if (!this.routeId) return;
            boton.disabled = true;
            boton.textContent = "Iniciando…";
            try {
                const res = await fetch(`/logistics/route/${this.routeId}/start`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: {} }),
                });
                const data = await res.json();
                if (data.result?.success) {
                    // El rastreo arranca ya, para no perder los primeros metros.
                    if (this.gpsTracker) this.gpsTracker.start();
                    this._showToast("🚀 Ruta iniciada", "success");
                    // Y se recarga para traer las paradas con su estado nuevo.
                    setTimeout(() => window.location.reload(), 900);
                } else {
                    boton.disabled = false;
                    boton.textContent = "🚀 INICIAR RUTA";
                    this._showToast(data.result?.error || "No se pudo iniciar la ruta.", "danger");
                }
            } catch (e) {
                boton.disabled = false;
                boton.textContent = "🚀 INICIAR RUTA";
                this._showToast("Sin conexión. Inténtelo de nuevo.", "warning");
            }
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
