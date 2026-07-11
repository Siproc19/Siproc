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
        help='Al registrar la muestra, el producto se transfiere a la '
             'ubicación "Muestras" y deja de estar disponible en bodega. '
             'Si regresa, se cancela y vuelve a bodega. Si se queda en '
             'prueba, se da de baja definitiva. Nunca se convierte en venta.',
    )
    sample_reference = fields.Char(
        string='Referencia de Muestra',
        readonly=True,
        copy=False,
    )
    sample_transfer_picking_id = fields.Many2one(
        'stock.picking',
        string='Traslado a Muestras',
        readonly=True,
        copy=False,
        help='Transferencia interna que movió el producto de bodega a la '
             'ubicación Muestras al registrar la orden.',
    )
    sample_return_picking_id = fields.Many2one(
        'stock.picking',
        string='Devolución a Bodega',
        readonly=True,
        copy=False,
        help='Transferencia que regresó el producto de Muestras a bodega '
             'cuando la muestra fue devuelta.',
    )
    sample_picking_id = fields.Many2one(
        'stock.picking',
        string='Salida Definitiva (Prueba)',
        readonly=True,
        copy=False,
        help='Salida que dio de baja el producto cuando la muestra se '
             'quedó en prueba con el cliente.',
    )

    # ------------------------------------------------------------------
    # Utilidades de inventario
    # ------------------------------------------------------------------
    def _get_sample_location(self):
        location = self.env.ref(
            'sale_sample_order.stock_location_samples_customer',
            raise_if_not_found=False)
        if not location:
            raise UserError(
                'No existe la ubicación de inventario "Muestras". '
                'Reinstala o actualiza el módulo Órdenes de Muestra.')
        return location

    def _get_sample_stock_lines(self):
        self.ensure_one()
        return self.order_line.filtered(
            lambda l: not l.display_type and l.product_id
            and l.product_id.type == 'consu' and l.product_uom_qty > 0)

    def _create_sample_picking(self, picking_type, location_src,
                               location_dest):
        """Crear una transferencia con las líneas de la muestra y validarla
        automáticamente si los productos no requieren lotes/series."""
        self.ensure_one()
        lines = self._get_sample_stock_lines()
        if not lines:
            return False
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
        tracked = any(l.product_id.tracking != 'none' for l in lines)
        if not tracked:
            for move in picking.move_ids:
                move.quantity = move.product_uom_qty
                move.picked = True
            picking.with_context(
                skip_backorder=True, skip_sms=True).button_validate()
        return picking

    # ------------------------------------------------------------------
    # Flujo de la orden de muestra
    # ------------------------------------------------------------------
    def _sample_send_to_location(self):
        """Bodega -> Muestras (tipo cliente): el producto se descuenta del
        stock disponible de toda la empresa."""
        self.ensure_one()
        if self.sample_transfer_picking_id:
            return self.sample_transfer_picking_id
        warehouse = self.warehouse_id
        if not warehouse or not warehouse.out_type_id:
            raise UserError(
                'No se encontró un almacén con tipo de operación de salida '
                'para trasladar el producto a Muestras.')
        picking = self._create_sample_picking(
            warehouse.out_type_id, warehouse.lot_stock_id,
            self._get_sample_location())
        if picking:
            self.sample_transfer_picking_id = picking
            if picking.state == 'done':
                self.message_post(
                    body='Producto trasladado a la ubicación Muestras '
                         '(traslado %s). Ya no aparece disponible en bodega.'
                         % picking.name)
            else:
                self.message_post(
                    body='Se generó el traslado %s a la ubicación Muestras. '
                         'Los productos llevan lotes/series: valídalo en '
                         'Inventario asignando los lotes.' % picking.name)
        return picking

    def _sample_return_to_stock(self):
        """Muestras -> Bodega (recepción): el producto regresó y vuelve a
        estar disponible."""
        self.ensure_one()
        if not self.sample_transfer_picking_id \
                or self.sample_return_picking_id:
            return False
        warehouse = self.warehouse_id
        if not warehouse or not warehouse.in_type_id:
            raise UserError(
                'No se encontró un almacén con tipo de operación de '
                'recepción para regresar el producto de Muestras.')
        picking = self._create_sample_picking(
            warehouse.in_type_id, self._get_sample_location(),
            warehouse.lot_stock_id)
        if picking:
            self.sample_return_picking_id = picking
            self.message_post(
                body='Producto devuelto: traslado %s de Muestras a bodega%s.'
                     % (picking.name,
                        '' if picking.state == 'done'
                        else ' (pendiente de validar lotes/series)'))
        return picking

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_sample_order'):
                if not vals.get('sample_reference'):
                    seq = self.env['ir.sequence'].next_by_code('sale.sample.order')
                    vals['sample_reference'] = seq or 'OM/'
                    if not vals.get('name') or vals.get('name') in ('/', 'New', 'Nuevo'):
                        vals['name'] = vals['sample_reference']
                if vals.get('state', 'draft') == 'draft':
                    vals['state'] = 'sample'
        orders = super().create(vals_list)
        for order in orders:
            if order.is_sample_order and order.state == 'sample':
                order._sample_send_to_location()
        return orders

    def write(self, vals):
        res = super().write(vals)
        if 'is_sample_order' in vals:
            for order in self:
                if vals['is_sample_order'] and order.state == 'draft':
                    super(SaleOrder, order).write({'state': 'sample'})
                    if not order.sample_reference:
                        seq = self.env['ir.sequence'].next_by_code('sale.sample.order')
                        order.sample_reference = seq or 'OM/'
                    order._sample_send_to_location()
                elif not vals['is_sample_order'] and order.state == 'sample':
                    order._sample_return_to_stock()
                    super(SaleOrder, order).write({'state': 'draft'})
        return res

    def action_sample_trial(self):
        """Muestras -> Cliente: baja definitiva, el producto no regresa."""
        for order in self:
            if order.state != 'sample':
                continue
            warehouse = order.warehouse_id
            if not warehouse or not warehouse.out_type_id:
                raise UserError(
                    'No se encontró un almacén con tipo de operación de '
                    'salida para dar de baja el producto en prueba.')
            # Si hubo traslado a Muestras, la baja sale de ahí; si no
            # (muestras antiguas), sale directo de bodega.
            if order.sample_transfer_picking_id:
                location_src = order._get_sample_location()
            else:
                location_src = warehouse.lot_stock_id
            picking = order._create_sample_picking(
                warehouse.out_type_id, location_src,
                order.partner_id.property_stock_customer)
            order.write({'state': 'sample_trial'})
            if picking:
                order.sample_picking_id = picking
                order.message_post(
                    body='Producto quedó en prueba con el cliente. Salida '
                         'definitiva %s%s.'
                         % (picking.name,
                            '' if picking.state == 'done'
                            else ' pendiente de validar lotes/series'))
            else:
                order.message_post(
                    body='Documento pasó a Orden de Prueba sin productos '
                         'almacenables; no se generó salida de inventario.')
        return True

    def action_sample_cancel(self):
        """Solo desde Orden de Muestra: el producto fue devuelto."""
        for order in self:
            if order.state != 'sample':
                raise UserError(
                    'Solo una Orden de Muestra puede cancelarse por '
                    'devolución. Una Orden de Prueba ya dio de baja el '
                    'producto y no admite devolución.')
            order._sample_return_to_stock()
            order.write({'state': 'cancel'})
            order.message_post(
                body='Producto de muestra devuelto. Documento %s cancelado.'
                     % (order.sample_reference or order.name))
        return True

    def action_confirm(self):
        for order in self:
            if order.is_sample_order:
                raise UserError(
                    'Una Orden de Muestra no puede confirmarse ni '
                    'convertirse en venta. Usa "Se Queda en Prueba" si el '
                    'producto no regresará (se dará de baja del inventario) '
                    'o "Producto Devuelto" si el cliente lo regresó.')
        return super().action_confirm()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _check_sample_locked(self):
        for line in self:
            order = line.order_id
            if order.is_sample_order and order.sample_transfer_picking_id \
                    and order.state in ('sample', 'sample_trial'):
                raise UserError(
                    'No se pueden modificar las líneas de una Orden de '
                    'Muestra ya registrada, porque el inventario ya fue '
                    'trasladado a Muestras. Si hubo un error, usa '
                    '"Producto Devuelto" para cancelarla (el stock regresa '
                    'a bodega) y crea una muestra nueva.')

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        # Bloquear solo si la muestra ya movió inventario (las líneas
        # iniciales se crean antes del traslado, así que no se bloquean).
        lines._check_sample_locked()
        return lines

    def write(self, vals):
        protected = {'product_id', 'product_uom_qty', 'product_uom_id'}
        if protected & set(vals.keys()):
            self._check_sample_locked()
        return super().write(vals)

    def unlink(self):
        self._check_sample_locked()
        return super().unlink()
