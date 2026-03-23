from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DeliveryVehicle(models.Model):
    _name = "delivery.vehicle"
    _description = "Vehículo de Entrega"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"

    name = fields.Char(string="Código Interno", required=True, tracking=True)
    plate = fields.Char(string="Placa", required=True, tracking=True)
    brand = fields.Char(string="Marca")
    model = fields.Char(string="Modelo")
    vehicle_type = fields.Selection(
        [
            ("panel", "Panel"),
            ("camion", "Camión"),
            ("pickup", "Pickup"),
            ("moto", "Moto"),
        ],
        string="Tipo de Vehículo",
        required=True,
        default="panel",
        tracking=True,
    )
    capacity = fields.Float(string="Capacidad")
    state = fields.Selection(
        [
            ("available", "Disponible"),
            ("in_route", "En Ruta"),
            ("maintenance", "Mantenimiento"),
            ("inactive", "Inactivo"),
        ],
        string="Estado",
        default="available",
        tracking=True,
    )

    driver_id = fields.Many2one("delivery.driver", string="Piloto Asignado")
    phone = fields.Char(string="Teléfono del Piloto", related="driver_id.phone", store=False)
    company_id = fields.Many2one("res.company", string="Compañía", default=lambda self: self.env.company)

    last_latitude = fields.Float(string="Última Latitud", digits=(10, 6))
    last_longitude = fields.Float(string="Última Longitud", digits=(10, 6))
    last_gps_datetime = fields.Datetime(string="Última Actualización GPS")

    route_ids = fields.One2many("delivery.route", "vehicle_id", string="Rutas")
    active_route_count = fields.Integer(compute="_compute_active_route_count")
    display_name = fields.Char(compute="_compute_display_name", store=True)

    @api.depends("name", "plate", "vehicle_type")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name or ''} - {rec.plate or ''}"

    @api.depends("route_ids.state")
    def _compute_active_route_count(self):
        for rec in self:
            rec.active_route_count = len(rec.route_ids.filtered(lambda r: r.state in ("planned", "in_progress", "partial")))

    @api.constrains("plate", "name")
    def _check_unique_fields(self):
        for rec in self:
            if rec.plate:
                dup_plate = self.search([("id", "!=", rec.id), ("plate", "=", rec.plate)], limit=1)
                if dup_plate:
                    raise ValidationError(_("La placa del vehículo debe ser única."))
            if rec.name:
                dup_name = self.search([("id", "!=", rec.id), ("name", "=", rec.name)], limit=1)
                if dup_name:
                    raise ValidationError(_("El código interno del vehículo debe ser único."))

    def action_set_available(self):
        self.write({"state": "available"})

    def action_set_maintenance(self):
        self.write({"state": "maintenance"})
