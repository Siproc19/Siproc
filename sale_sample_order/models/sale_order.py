# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_sample_order = fields.Boolean(
        string='Orden de Muestra',
        copy=False,
        tracking=True,
        help='Marca este documento como una salida de producto de muestra. '
             'Mientras esté en borrador o enviada NO afecta el inventario. '
             'Si el cliente se queda con el producto, confirma la orden y se '
             'convierte en una orden de venta normal.',
    )
    sample_reference = fields.Char(
        string='Referencia de Muestra',
        readonly=True,
        copy=False,
        help='Número OM original asignado cuando se creó como orden de muestra.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Asignar numeración propia OM-xxxxx a las órdenes de muestra."""
        for vals in vals_list:
            if vals.get('is_sample_order') and not vals.get('sample_reference'):
                seq = self.env['ir.sequence'].next_by_code('sale.sample.order')
                vals['sample_reference'] = seq or 'OM/'
                # Usar la referencia OM como nombre del documento si aún no
                # tiene numeración (evita que tome la secuencia S00xxx).
                if not vals.get('name') or vals.get('name') in ('/', 'New', 'Nuevo'):
                    vals['name'] = vals['sample_reference']
        return super().create(vals_list)

    def action_confirm(self):
        """Al confirmar una orden de muestra, pasa a numeración normal de
        orden de venta y conserva la referencia OM para trazabilidad."""
        for order in self:
            if order.is_sample_order and order.sample_reference \
                    and order.name == order.sample_reference:
                new_name = self.env['ir.sequence'].next_by_code('sale.order')
                if new_name:
                    order.message_post(
                        body='Orden de muestra %s confirmada como venta %s.'
                             % (order.sample_reference, new_name)
                    )
                    order.name = new_name
        return super().action_confirm()
