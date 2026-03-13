from odoo import fields, models


class DeliveryDriver(models.Model):
    _name = "delivery.driver"
    _description = "Piloto / Repartidor"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"

    name = fields.Char(string="Nombre", required=True, tracking=True)
    employee_id = fields.Many2one("hr.employee", string="Empleado")
    user_id = fields.Many2one("res.users", string="Usuario Odoo")
    phone = fields.Char(string="Teléfono")
    license_number = fields.Char(string="Licencia")
    state = fields.Selection(
        [
            ("available", "Disponible"),
            ("in_route", "En Ruta"),
            ("suspended", "Suspendido"),
            ("inactive", "Inactivo"),
        ],
        string="Estado",
        default="available",
        tracking=True,
    )

    vehicle_id = fields.Many2one("delivery.vehicle", string="Vehículo Asignado")
    route_ids = fields.One2many("delivery.route", "driver_id", string="Rutas")
    active_route_count = fields.Integer(compute="_compute_active_route_count")

    def _compute_active_route_count(self):
        for rec in self:
            rec.active_route_count = len(rec.route_ids.filtered(lambda r: r.state in ("planned", "in_progress", "partial")))
