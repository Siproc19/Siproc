from odoo import fields, models


class DeliveryGpsLog(models.Model):
    _name = "delivery.gps.log"
    _description = "Historial GPS de Entregas"
    _order = "gps_datetime desc"

    route_id = fields.Many2one("delivery.route", string="Ruta", ondelete="cascade")
    vehicle_id = fields.Many2one("delivery.vehicle", string="Vehículo")
    driver_id = fields.Many2one("delivery.driver", string="Piloto")
    user_id = fields.Many2one("res.users", string="Usuario")
    latitude = fields.Float(string="Latitud", required=True, digits=(10, 6))
    longitude = fields.Float(string="Longitud", required=True, digits=(10, 6))
    speed = fields.Float(string="Velocidad")
    gps_datetime = fields.Datetime(string="Fecha/Hora GPS", required=True, default=fields.Datetime.now)
    delivery_line_id = fields.Many2one("delivery.route.line", string="Punto de Entrega")
    note = fields.Char(string="Nota")
