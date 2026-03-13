from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    x_delivery_route_id = fields.Many2one("delivery.route", string="Ruta de Entrega")
    x_delivery_route_line_id = fields.Many2one("delivery.route.line", string="Línea de Ruta")
    x_delivery_status = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("on_the_way", "En camino"),
            ("delivered", "Entregado"),
            ("rejected", "Rechazado"),
            ("rescheduled", "Reprogramado"),
            ("not_found", "No localizado"),
        ],
        string="Estado de Entrega",
        default="pending",
    )
    x_delivered_at = fields.Datetime(string="Fecha/Hora Entrega")
    x_delivered_latitude = fields.Float(string="Latitud Entrega", digits=(10, 6))
    x_delivered_longitude = fields.Float(string="Longitud Entrega", digits=(10, 6))
    x_receiver_name = fields.Char(string="Recibido por")
