# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class PurchaseOrder(models.Model):
    """Visibilidad de la logística en la orden de compra."""
    _inherit = 'purchase.order'

    logistics_task_ids = fields.One2many(
        'logistics.task', 'purchase_order_id',
        string='Paradas de Ruta', copy=False,
    )
    logistics_task_count = fields.Integer(
        string='Paradas', compute='_compute_logistics_task_count',
    )
    logistics_status = fields.Selection([
        ('no_route', 'Sin Ruta'),
        ('planned', 'Ruta Planificada'),
        ('in_transit', 'En Camino'),
        ('done', 'Realizada'),
        ('failed', 'No Realizada'),
    ], string='Estado Logístico', compute='_compute_logistics_status')

    @api.depends('logistics_task_ids')
    def _compute_logistics_task_count(self):
        for rec in self:
            rec.logistics_task_count = len(rec.logistics_task_ids)

    @api.depends('logistics_task_ids.state')
    def _compute_logistics_status(self):
        for rec in self:
            states = set(rec.logistics_task_ids.mapped('state'))
            if not states:
                rec.logistics_status = 'no_route'
            elif states == {'completed'}:
                rec.logistics_status = 'done'
            elif states == {'failed'}:
                rec.logistics_status = 'failed'
            elif states & {'in_transit', 'arrived'}:
                rec.logistics_status = 'in_transit'
            else:
                rec.logistics_status = 'planned'

    def action_view_logistics_routes(self):
        """Abre la ruta que lleva esta compra."""
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
