/** @odoo-module **/
/**
 * visit_management/static/src/js/visit_dashboard.js
 * Dashboard interactivo para KPIs de visitas comerciales
 */

import { registry } from "@web/core/registry";
import { Component, onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class VisitDashboard extends Component {
    static template = "visit_management.VisitDashboard";

    setup() {
        this.rpc   = useService("rpc");
        this.state = useState({
            loading:          true,
            totalVisitas:     0,
            visitasHoy:       0,
            visitasFinalizadas: 0,
            tasaCumplimiento: 0,
            kmTotal:          0,
            costoTotal:       0,
            topAsesores:      [],
        });

        onMounted(() => this._loadKPIs());
    }

    async _loadKPIs() {
        try {
            // Cargar estadísticas desde el servidor
            const result = await this.rpc("/visit_management/dashboard_kpis", {});
            if (result) {
                Object.assign(this.state, result, { loading: false });
            }
        } catch (e) {
            console.error("Error cargando KPIs:", e);
            this.state.loading = false;
        }
    }
}

registry.category("actions").add("visit_management.dashboard", VisitDashboard);
