# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    state = fields.Selection(
        selection_add=[('sample', 'Orden de Muestra'), ('draft',)],
        ondelete={'sample': 'set default'},
    )
    is_sample_order = fields.Boolean(
        string='Orden de Muestra',
        copy=False,
        tracking=True,
        help='Marca este documento como una salida de producto de muestra. '
             'Mientras esté como Orden de Muestra, Cotización o Cotización '
             'enviada NO afecta el inventario. Si el cliente se queda con el '
             'producto, se convierte en una orden de venta normal.',
    )
    sample_reference = fields.Char(
        string='Referencia de Muestra',
        readonly=True,
        copy=False,
        help='Número OM original asignado cuando se creó como orden de muestra.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Numeración OM-xxxxx y estado inicial 'Orden de Muestra'."""
        for vals in vals_list:
            if vals.get('is_sample_order'):
                if not vals.get('sample_reference'):
                    seq = self.env['ir.sequence'].next_by_code('sale.sample.order')
                    vals['sample_reference'] = seq or 'OM/'
                    if not vals.get('name') or vals.get('name') in ('/', 'New', 'Nuevo'):
                        vals['name'] = vals['sample_reference']
                if vals.get('state', 'draft') == 'draft':
                    vals['state'] = 'sample'
        return super().create(vals_list)

    def write(self, vals):
        """Si se marca la casilla en una cotización existente, pasa al estado
        Orden de Muestra (y al desmarcarla, regresa a Cotización)."""
        res = super().write(vals)
        if 'is_sample_order' in vals:
            for order in self:
                if vals['is_sample_order'] and order.state == 'draft':
                    super(SaleOrder, order).write({'state': 'sample'})
                    if not order.sample_reference:
                        seq = self.env['ir.sequence'].next_by_code('sale.sample.order')
                        order.sample_reference = seq or 'OM/'
                elif not vals['is_sample_order'] and order.state == 'sample':
                    super(SaleOrder, order).write({'state': 'draft'})
        return res

    def action_convert_to_quotation(self):
        """Botón: pasar de Orden de Muestra a Cotización (flujo estándar)."""
        for order in self:
            if order.state == 'sample':
                order.write({'state': 'draft'})
                order.message_post(
                    body='Orden de muestra %s convertida a cotización.'
                         % (order.sample_reference or order.name)
                )
        return True

    def action_confirm(self):
        """Al confirmar, asignar numeración normal de orden de venta y
        conservar la referencia OM para trazabilidad."""
        # Si confirman directo desde el estado muestra, pasarla antes a draft
        self.filtered(lambda o: o.state == 'sample').write({'state': 'draft'})
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
