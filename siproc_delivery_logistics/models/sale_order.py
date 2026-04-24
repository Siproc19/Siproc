from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    delivery_route_line_ids = fields.One2many("delivery.route.line", "sale_order_id", string="Líneas Logísticas")
    delivery_route_count = fields.Integer(compute="_compute_delivery_route_count")
    x_delivery_logistics_status = fields.Selection(
        [
            ("no_route", "Sin Ruta"),
            ("planned", "Planificada"),
            ("in_progress", "En Ruta"),
            ("partial", "Parcial"),
            ("delivered", "Entregada"),
        ],
        string="Estado Logístico",
        compute="_compute_delivery_logistics_status",
        store=False,
    )
    x_delivery_date = fields.Date(string="Fecha Programada de Entrega", compute="_compute_delivery_info", store=False)
    x_delivery_vehicle_id = fields.Many2one("delivery.vehicle", string="Vehículo", compute="_compute_delivery_info", store=False)
    x_delivery_driver_id = fields.Many2one("delivery.driver", string="Piloto", compute="_compute_delivery_info", store=False)

    def _compute_delivery_route_count(self):
        for rec in self:
            rec.delivery_route_count = len(rec.delivery_route_line_ids.mapped("route_id"))

    @api.depends("delivery_route_line_ids.delivery_status", "delivery_route_line_ids.route_id.state")
    def _compute_delivery_logistics_status(self):
        for rec in self:
            if not rec.delivery_route_line_ids:
                rec.x_delivery_logistics_status = "no_route"
                continue

            statuses = rec.delivery_route_line_ids.mapped("delivery_status")
            route_states = rec.delivery_route_line_ids.mapped("route_id.state")

            if statuses and all(s == "delivered" for s in statuses):
                rec.x_delivery_logistics_status = "delivered"
            elif any(s == "delivered" for s in statuses):
                rec.x_delivery_logistics_status = "partial"
            elif any(s == "on_the_way" for s in statuses) or any(s in ("in_progress", "partial") for s in route_states):
                rec.x_delivery_logistics_status = "in_progress"
            else:
                rec.x_delivery_logistics_status = "planned"

    @api.depends("delivery_route_line_ids.route_id.date", "delivery_route_line_ids.route_id.vehicle_id", "delivery_route_line_ids.route_id.driver_id")
    def _compute_delivery_info(self):
        for rec in self:
            line = rec.delivery_route_line_ids[:1]
            rec.x_delivery_date = line.route_id.date if line else False
            rec.x_delivery_vehicle_id = line.route_id.vehicle_id if line else False
            rec.x_delivery_driver_id = line.route_id.driver_id if line else False

    def action_view_delivery_routes(self):
        self.ensure_one()
        routes = self.delivery_route_line_ids.mapped("route_id")
        action = self.env.ref("siproc_delivery_logistics.delivery_route_action").read()[0]
        if len(routes) == 1:
            action["res_id"] = routes.id
            action["views"] = [(self.env.ref("siproc_delivery_logistics.delivery_route_view_form").id, "form")]
        else:
            action["domain"] = [("id", "in", routes.ids)]
        return action
