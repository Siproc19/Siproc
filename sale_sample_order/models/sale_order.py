# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    state = fields.Selection(
        selection_add=[
            ('sample', 'Orden de Muestra'),
            ('sample_trial', 'Orden de Prueba'),
            ('draft',),
        ],
        ondelete={'sample': 'set default', 'sample_trial': 'set default'},
    )
    is_sample_order = fields.Boolean(
        string='Orden de Muestra',
        copy=False,
        tracking=True,
        help='Documento de control de producto en muestra. Flujo propio: '
             'Orden de Muestra (el producto puede regresar) > Orden de '
             'Prueba (el producto se queda con el cliente y se da de baja '
             'del inventario). Nunca se convierte en cotización ni orden '
             'de venta.',
    )
    sample_reference = fields.Char(
        string='Referencia de Muestra',
        readonly=True,
        copy=False,
    )
    sample_picking_id = fields.Many2one(
        'stock.picking',
        string='Salida de Inventario (Prueba)',
        readonly=True,
        copy=False,
        help='Entrega que dio de baja el producto del inventario cuando '
             'la muestra se quedó en prueba con el cliente.',
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
        """Marcar/desmarcar la casilla en una cotización mueve el documento
        entre el flujo de muestra y el de cotización (solo en borrador)."""
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

    # ------------------------------------------------------------------
    # Flujo propio de la orden de muestra
    # ------------------------------------------------------------------
    def _get_sample_stock_lines(self):
        """Líneas con producto almacenable/consumible (excluye servicios,
        secciones y notas)."""
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: not l.display_type and l.product_id
            and l.product_id.type == 'consu' and l.product_uom_qty > 0)

    def _create_sample_delivery(self):
        """Crear y validar la salida de inventario hacia el cliente para
        dar de baja el producto que se queda en prueba."""
        self.ensure_one()
        lines = self._get_sample_stock_lines()
        if not lines:
            return False
        warehouse = self.warehouse_id
        if not warehouse or not warehouse.out_type_id:
            raise UserError(
                'No se encontró un almacén con tipo de operación de salida '
                'para dar de baja el producto en prueba.')
        picking_type = warehouse.out_type_id
        location_src = picking_type.default_location_src_id
        location_dest = self.partner_id.property_stock_customer
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'partner_id': (self.partner_shipping_id or self.partner_id).id,
            'origin': self.sample_reference or self.name,
            'location_id': location_src.id,
            'location_dest_id': location_dest.id,
            'move_ids': [(0, 0, {
                'product_id': line.product_id.id,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.product_uom_id.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
            }) for line in lines],
        })
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.with_context(
            skip_backorder=True, skip_sms=True).button_validate()
        return picking

    def action_sample_trial(self):
        """El producto se queda en prueba: pasa a Orden de Prueba y se da
        de baja del inventario (ese producto ya no regresa)."""
        for order in self:
            if order.state != 'sample':
                continue
            picking = order._create_sample_delivery()
            order.write({'state': 'sample_trial'})
            if picking:
                order.sample_picking_id = picking
                order.message_post(
                    body='Producto quedó en prueba con el cliente. Se generó '
                         'la salida de inventario %s (baja definitiva).'
                         % picking.name)
            else:
                order.message_post(
                    body='Documento pasó a Orden de Prueba. No se generó '
                         'salida de inventario (sin productos almacenables).')
        return True

    def action_sample_cancel(self):
        """Solo desde Orden de Muestra: el producto fue devuelto."""
        for order in self:
            if order.state != 'sample':
                raise UserError(
                    'Solo una Orden de Muestra puede cancelarse por '
                    'devolución. Una Orden de Prueba ya dio de baja el '
                    'producto y no admite devolución.')
            order.write({'state': 'cancel'})
            order.message_post(
                body='Producto de muestra devuelto. Documento %s cancelado.'
                     % (order.sample_reference or order.name))
        return True

    def action_confirm(self):
        """Las órdenes de muestra nunca se confirman como venta."""
        for order in self:
            if order.is_sample_order:
                raise UserError(
                    'Una Orden de Muestra no puede confirmarse ni '
                    'convertirse en venta. Usa "Se Queda en Prueba" si el '
                    'producto no regresará (se dará de baja del inventario) '
                    'o "Producto Devuelto" si el cliente lo regresó.')
        return super().action_confirm()
