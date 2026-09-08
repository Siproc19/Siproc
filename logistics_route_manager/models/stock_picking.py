# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

# Mismo criterio que en ventas y compras: los enlaces directos a registros
# de logística quedan para los grupos del módulo; el resumen lo ve
# cualquier usuario de Inventario sin necesitar acceso al módulo.
GRUPOS_LOGISTICA = (
    'logistics_route_manager.group_logistics_manager,'
    'logistics_route_manager.group_logistics_user,'
    'logistics_route_manager.group_logistics_driver'
)


class StockPicking(models.Model):
    """
    Enlace de la orden de entrega con la logística de SIPROC.

    Guarda la prueba de la entrega tal como ocurrió en campo: quién la llevó,
    en qué ruta, a qué hora y en qué coordenadas GPS se marcó como entregada.
    """
    _inherit = 'stock.picking'

    x_logistics_task_id = fields.Many2one(
        'logistics.task', string='Parada de Ruta',
        copy=False, readonly=True,
        groups=GRUPOS_LOGISTICA,
    )
    x_logistics_route_id = fields.Many2one(
        'logistics.route', string='Ruta Logística',
        copy=False, readonly=True,
    )
    x_logistics_driver_id = fields.Many2one(
        'logistics.driver', string='Piloto',
        related='x_logistics_route_id.driver_id', store=True, readonly=True,
    )
    x_logistics_vehicle_id = fields.Many2one(
        'logistics.vehicle', string='Vehículo',
        related='x_logistics_route_id.vehicle_id', store=True, readonly=True,
    )
    x_logistics_date = fields.Date(
        string='Fecha de Ruta',
        related='x_logistics_route_id.date', store=True, readonly=True,
    )

    # Nombres en texto: dicen lo mismo que los enlaces de arriba, pero no
    # obligan a leer los modelos de logística.
    x_logistics_route_name = fields.Char(
        string='Ruta', compute='_compute_logistics_nombres',
    )
    x_logistics_driver_name = fields.Char(
        string='Piloto de Entrega', compute='_compute_logistics_nombres',
    )
    x_logistics_vehicle_name = fields.Char(
        string='Vehículo de Entrega', compute='_compute_logistics_nombres',
    )

    x_delivery_status = fields.Selection([
        ('no_route', 'Sin Ruta'),
        ('planned', 'En Ruta Planificada'),
        ('in_transit', 'En Camino'),
        ('delivered', 'Entregado'),
        ('failed', 'No Entregado'),
    ], string='Estado de Entrega', default='no_route', copy=False, readonly=True,
        tracking=True)

    x_delivered_at = fields.Datetime(
        string='Fecha/Hora de Entrega', copy=False, readonly=True,
    )
    x_delivered_latitude = fields.Float(
        string='Latitud de Entrega', digits=(10, 7), copy=False, readonly=True,
    )
    x_delivered_longitude = fields.Float(
        string='Longitud de Entrega', digits=(10, 7), copy=False, readonly=True,
    )
    x_receiver_name = fields.Char(
        string='Recibido por', copy=False, readonly=True,
    )
    x_delivery_proof_url = fields.Char(
        string='Ubicación de la Entrega',
        compute='_compute_delivery_proof_url',
    )
    x_has_logistics_route = fields.Boolean(
        compute='_compute_has_logistics_route', store=True,
    )

    @api.depends('x_logistics_route_id')
    def _compute_has_logistics_route(self):
        for rec in self:
            rec.x_has_logistics_route = bool(rec.sudo().x_logistics_route_id)

    @api.depends('x_logistics_route_id')
    def _compute_logistics_nombres(self):
        for rec in self:
            ruta = rec.sudo().x_logistics_route_id
            rec.x_logistics_route_name   = ruta.name if ruta else False
            rec.x_logistics_driver_name  = ruta.driver_id.name if ruta else False
            rec.x_logistics_vehicle_name = (
                ruta.vehicle_id.display_name if ruta else False
            )

    @api.depends('x_delivered_latitude', 'x_delivered_longitude')
    def _compute_delivery_proof_url(self):
        for rec in self:
            if rec.x_delivered_latitude and rec.x_delivered_longitude:
                rec.x_delivery_proof_url = (
                    f"https://www.google.com/maps?q="
                    f"{rec.x_delivered_latitude},{rec.x_delivered_longitude}"
                )
            else:
                rec.x_delivery_proof_url = False

    def action_open_logistics_route(self):
        """Abre la ruta en la que va esta entrega."""
        self.ensure_one()
        if not self.x_logistics_route_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ruta Logística'),
            'res_model': 'logistics.route',
            'res_id': self.x_logistics_route_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_delivery_location(self):
        """Abre en el mapa el punto exacto donde se marcó la entrega."""
        self.ensure_one()
        if not self.x_delivery_proof_url:
            return False
        return {
            'type': 'ir.actions.act_url',
            'url': self.x_delivery_proof_url,
            'target': 'new',
        }
