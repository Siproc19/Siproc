# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SaleOrder(models.Model):
    """
    Visibilidad logística en el pedido de venta.

    Ventas puede responderle al cliente "¿ya salió mi pedido?" sin llamar a
    Bodega: ve la ruta, el piloto, el vehículo y el estado de la entrega
    directamente en el pedido.
    """
    _inherit = 'sale.order'

    logistics_task_ids = fields.One2many(
        'logistics.task', 'sale_order_id',
        string='Paradas de Ruta', copy=False,
    )
    logistics_route_count = fields.Integer(
        string='Rutas', compute='_compute_logistics_route_count',
    )
    logistics_status = fields.Selection([
        ('no_route', 'Sin Ruta'),
        ('planned', 'Ruta Planificada'),
        ('in_transit', 'En Camino'),
        ('partial', 'Entrega Parcial'),
        ('delivered', 'Entregado'),
        ('failed', 'No Entregado'),
    ], string='Estado Logístico', compute='_compute_logistics_status')

    logistics_route_date = fields.Date(
        string='Fecha de Ruta', compute='_compute_logistics_info',
    )
    logistics_driver_id = fields.Many2one(
        'logistics.driver', string='Piloto Asignado',
        compute='_compute_logistics_info',
    )
    logistics_vehicle_id = fields.Many2one(
        'logistics.vehicle', string='Vehículo Asignado',
        compute='_compute_logistics_info',
    )
    logistics_delivered_at = fields.Datetime(
        string='Entregado el', compute='_compute_logistics_info',
    )

    @api.depends('logistics_task_ids.route_id')
    def _compute_logistics_route_count(self):
        for rec in self:
            rec.logistics_route_count = len(rec.logistics_task_ids.mapped('route_id'))

    @api.depends('logistics_task_ids.state', 'logistics_task_ids.route_id.state')
    def _compute_logistics_status(self):
        for rec in self:
            tasks = rec.logistics_task_ids
            if not tasks:
                rec.logistics_status = 'no_route'
                continue
            states = set(tasks.mapped('state'))
            if states == {'completed'}:
                rec.logistics_status = 'delivered'
            elif states == {'failed'}:
                rec.logistics_status = 'failed'
            elif 'completed' in states:
                rec.logistics_status = 'partial'
            elif states & {'in_transit', 'arrived'}:
                rec.logistics_status = 'in_transit'
            elif 'in_progress' in set(tasks.mapped('route_id.state')):
                rec.logistics_status = 'in_transit'
            else:
                rec.logistics_status = 'planned'

    @api.depends(
        'logistics_task_ids.route_id.date',
        'logistics_task_ids.route_id.driver_id',
        'logistics_task_ids.route_id.vehicle_id',
        'logistics_task_ids.actual_departure',
    )
    def _compute_logistics_info(self):
        for rec in self:
            # La parada más reciente manda: es la que refleja el estado actual.
            task = rec.logistics_task_ids.sorted(
                lambda t: (t.route_id.date or fields.Date.today(), t.id), reverse=True
            )[:1]
            route = task.route_id if task else False
            rec.logistics_route_date = route.date if route else False
            rec.logistics_driver_id = route.driver_id if route else False
            rec.logistics_vehicle_id = route.vehicle_id if route else False
            delivered = rec.logistics_task_ids.filtered(
                lambda t: t.state == 'completed' and t.actual_departure
            ).sorted('actual_departure', reverse=True)[:1]
            rec.logistics_delivered_at = delivered.actual_departure if delivered else False

    def action_view_logistics_routes(self):
        """Abre la ruta (o las rutas) que llevan este pedido."""
        self.ensure_one()
        routes = self.logistics_task_ids.mapped('route_id')
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Rutas Logísticas'),
            'res_model': 'logistics.route',
            'target': 'current',
        }
        if len(routes) == 1:
            action.update({'res_id': routes.id, 'view_mode': 'form'})
        else:
            action.update({
                'domain': [('id', 'in', routes.ids)],
                'view_mode': 'list,form',
            })
        return action
