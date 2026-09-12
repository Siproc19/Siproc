# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class LogisticsTask(models.Model):
    """
    Tarea / Parada dentro de una ruta logística.
    Tipos: Entrega, Compra, Mandado, Banco.
    """
    _name = 'logistics.task'
    _description = 'Tarea Logística'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'route_id, sequence, id'

    # ── Campos generales ─────────────────────────────────────────────────────
    name = fields.Char(string='Descripción', required=True, tracking=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    route_id = fields.Many2one(
        'logistics.route', string='Ruta',
        ondelete='cascade', tracking=True,
    )
    task_type = fields.Selection([
        ('delivery', '📦 Entrega de Productos'),
        ('purchase', '🛒 Compra de Productos'),
        ('errand', '📋 Mandado'),
        ('bank', '🏦 Banco'),
    ], string='Tipo de Tarea', required=True, default='delivery', tracking=True)

    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('in_transit', 'En Camino'),
        ('arrived', 'Llegó'),
        ('completed', '✅ Completado'),
        ('failed', '❌ Fallido'),
    ], string='Estado', default='pending', tracking=True)

    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Alta'),
        ('2', 'Urgente'),
    ], string='Prioridad', default='0')

    # ── Ubicación ─────────────────────────────────────────────────────────────
    partner_id = fields.Many2one(
        'res.partner', string='Cliente / Contacto',
        help='Al seleccionarlo se copian su dirección, teléfono y coordenadas.',
        tracking=True,
    )
    location_id = fields.Many2one(
        'logistics.location', string='Lugar Registrado',
        help='Seleccione un lugar frecuente o ingrese la dirección manualmente',
    )
    address = fields.Char(string='Dirección', tracking=True)
    latitude = fields.Float(string='Latitud', digits=(10, 7))
    longitude = fields.Float(string='Longitud', digits=(10, 7))

    # ── Tiempos ───────────────────────────────────────────────────────────────
    estimated_arrival = fields.Datetime(string='Llegada Estimada')
    actual_arrival = fields.Datetime(string='Llegada Real', readonly=True)
    actual_departure = fields.Datetime(string='Salida Real', readonly=True)
    time_at_location = fields.Float(
        string='Tiempo en Lugar (min)',
        compute='_compute_time_at_location',
    )

    # ── Contacto ──────────────────────────────────────────────────────────────
    contact_name = fields.Char(string='Nombre de Contacto')
    contact_phone = fields.Char(string='Teléfono')
    notes = fields.Text(string='Instrucciones / Notas')
    failure_reason = fields.Text(string='Razón de Fallo')

    # ── Evidencias ────────────────────────────────────────────────────────────
    evidence_photo_1 = fields.Binary(string='Foto de Evidencia 1')
    evidence_photo_2 = fields.Binary(string='Foto de Evidencia 2')
    evidence_photo_3 = fields.Binary(string='Foto de Evidencia 3')
    signature = fields.Binary(string='Firma Digital del Receptor')
    signature_name = fields.Char(string='Nombre del Firmante')

    # ── Campos específicos: ENTREGA ───────────────────────────────────────────
    stock_picking_id = fields.Many2one(
        'stock.picking', string='Orden de Entrega (Stock)',
        domain=[('picking_type_code', '=', 'outgoing')],
        index=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order', string='Pedido de Venta',
        index=True,
        help='Se completa solo al elegir la orden de entrega.',
    )
    delivery_products = fields.Text(string='Productos a Entregar')
    delivery_weight_kg = fields.Float(string='Peso Total (kg)')

    # ── Campos específicos: COMPRA ────────────────────────────────────────────
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Orden de Compra',
    )
    shopping_list = fields.Text(string='Lista de Compras')
    authorized_amount = fields.Float(string='Monto Autorizado (Q)')
    spent_amount = fields.Float(string='Monto Gastado (Q)')
    invoice_photo = fields.Binary(string='Foto de Factura')

    # ── Campos específicos: MANDADO ───────────────────────────────────────────
    errand_description = fields.Text(string='Descripción del Mandado')
    requested_by = fields.Many2one('res.users', string='Solicitado por')
    errand_amount = fields.Float(string='Monto para Gastos (Q)')

    # ── Campos específicos: BANCO ─────────────────────────────────────────────
    bank_name = fields.Char(string='Banco')
    bank_transaction_type = fields.Selection([
        ('deposit', 'Depósito'),
        ('withdrawal', 'Retiro'),
        ('transfer', 'Transferencia'),
        ('payment', 'Pago'),
        ('other', 'Otro Trámite'),
    ], string='Tipo de Trámite')
    bank_amount = fields.Float(string='Monto (Q)')
    account_number = fields.Char(string='Número de Cuenta')
    bank_voucher = fields.Binary(string='Comprobante Bancario')

    # ── Computed ──────────────────────────────────────────────────────────────
    @api.depends('actual_arrival', 'actual_departure')
    def _compute_time_at_location(self):
        for rec in self:
            if rec.actual_arrival and rec.actual_departure:
                delta = rec.actual_departure - rec.actual_arrival
                rec.time_at_location = delta.total_seconds() / 60
            else:
                rec.time_at_location = 0.0

    @api.onchange('location_id')
    def _onchange_location_id(self):
        """Al seleccionar un lugar frecuente, autocompleta dirección y coordenadas."""
        if self.location_id:
            self.address = self.location_id.address
            self.latitude = self.location_id.latitude
            self.longitude = self.location_id.longitude
            self.contact_name = self.location_id.contact_name
            self.contact_phone = self.location_id.contact_phone

    # ── Autocompletado desde los documentos ───────────────────────────────────
    def _vals_from_partner(self, partner):
        """Dirección, contacto y coordenadas de un contacto de Odoo."""
        if not partner:
            return {}
        vals = {
            'address': partner._display_address(without_company=True).replace('\n', ', ')
            if hasattr(partner, '_display_address') else (partner.contact_address or ''),
            'contact_name': partner.name,
            'contact_phone': partner.phone
            or (partner.mobile if 'mobile' in partner._fields else '')
            or '',
        }
        lat = partner.partner_latitude if 'partner_latitude' in partner._fields else 0.0
        lng = partner.partner_longitude if 'partner_longitude' in partner._fields else 0.0
        if lat and lng:
            vals['latitude'] = lat
            vals['longitude'] = lng
        return vals

    def _vals_from_picking(self, picking):
        """Cliente, dirección y contenido de una orden de entrega."""
        if not picking:
            return {}
        partner = picking.partner_id
        vals = {
            'task_type': 'delivery',
            'partner_id': partner.id if partner else False,
            'name': _('Entrega %(ref)s — %(partner)s',
                      ref=picking.name, partner=partner.name or ''),
            'delivery_products': self._summarize_picking_lines(picking),
            'delivery_weight_kg': self._picking_weight(picking),
        }
        # `sale_id` solo existe si sale_stock está instalado.
        if 'sale_id' in picking._fields and picking.sale_id:
            vals['sale_order_id'] = picking.sale_id.id
        vals.update(self._vals_from_partner(partner))
        if picking.note:
            vals['notes'] = picking.note
        return vals

    @api.model
    def _summarize_picking_lines(self, picking):
        """Resumen legible de lo que va en la entrega, para el piloto."""
        lines = []
        for move in picking.move_ids:
            qty = move.product_uom_qty
            uom = move.product_uom.name if move.product_uom else ''
            lines.append(f"{qty:g} {uom} — {move.product_id.display_name}".strip())
        return "\n".join(lines)

    @api.model
    def _picking_weight(self, picking):
        """Peso total de la entrega, si los productos lo tienen configurado."""
        total = 0.0
        for move in picking.move_ids:
            weight = getattr(move.product_id, 'weight', 0.0) or 0.0
            total += weight * move.product_uom_qty
        return total

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Copia dirección, teléfono y coordenadas del cliente."""
        if self.partner_id:
            self.update(self._vals_from_partner(self.partner_id))

    @api.onchange('stock_picking_id')
    def _onchange_stock_picking_id(self):
        """Rellena la parada con los datos de la orden de entrega."""
        if self.stock_picking_id:
            self.update(self._vals_from_picking(self.stock_picking_id))

    @api.onchange('purchase_order_id')
    def _onchange_purchase_order_id(self):
        """Rellena la parada con los datos de la orden de compra."""
        order = self.purchase_order_id
        if not order:
            return
        vals = {
            'task_type': 'purchase',
            'partner_id': order.partner_id.id if order.partner_id else False,
            'name': _('Compra %(ref)s — %(partner)s',
                      ref=order.name, partner=order.partner_id.name or ''),
            'authorized_amount': order.amount_total,
            'shopping_list': "\n".join(
                f"{line.product_qty:g} — {line.product_id.display_name}"
                for line in order.order_line
            ),
        }
        vals.update(self._vals_from_partner(order.partner_id))
        self.update(vals)

    # ── Sincronización de estado con la orden de entrega ──────────────────────
    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals:
            self._sync_picking_transit_status()
        return res

    def _sync_picking_transit_status(self):
        """
        Refleja en la orden de entrega que ya va en camino.

        Se usa sudo: el piloto actualiza su parada desde el celular y no
        necesariamente tiene permisos de escritura en Inventario. Es una
        sincronización del sistema, no una acción del usuario sobre el stock.
        """
        for task in self:
            picking = task.stock_picking_id
            if not picking:
                continue
            if task.state in ('in_transit', 'arrived'):
                if picking.x_delivery_status in ('no_route', 'planned'):
                    picking.sudo().x_delivery_status = 'in_transit'
            elif task.state == 'pending':
                if picking.x_delivery_status == 'in_transit':
                    picking.sudo().x_delivery_status = 'planned'

    # ── Acciones de estado ────────────────────────────────────────────────────
    def action_mark_arrived(self):
        """Piloto marcó que llegó a la parada."""
        self.ensure_one()
        self.write({
            'state': 'arrived',
            'actual_arrival': fields.Datetime.now(),
        })
        # Notificar bus
        self.env['bus.bus']._sendone(
            f'logistics_task_{self.route_id.id}',
            'task_arrived',
            {'task_id': self.id, 'task_name': self.name}
        )

    def action_mark_completed(self):
        """Piloto completó la tarea."""
        self.ensure_one()
        self.write({
            'state': 'completed',
            'actual_departure': fields.Datetime.now(),
        })
        self._sync_delivery_document()
        self._avisar_a_ventas_y_crm(entregado=True)
        self.env['bus.bus']._sendone(
            f'logistics_task_{self.route_id.id}',
            'task_completed',
            {'task_id': self.id, 'task_name': self.name}
        )

    # ── Devolución de la entrega al documento de origen ───────────────────────
    def _sync_delivery_document(self):
        """
        Escribe en la orden de entrega la prueba de la entrega: fecha y hora
        reales, coordenadas GPS donde el piloto la marcó, y quién recibió.

        Si el ajuste correspondiente está activo, además intenta validar la
        transferencia. Un fallo de validación (falta de stock, por ejemplo)
        se registra en el chatter pero nunca bloquea al piloto: su trabajo en
        campo ya está hecho.
        """
        self.ensure_one()
        picking = self.stock_picking_id
        if not picking:
            return

        driver = self.route_id.driver_id
        picking = picking.sudo()
        picking.write({
            'x_logistics_task_id': self.id,
            'x_logistics_route_id': self.route_id.id,
            'x_delivery_status': 'delivered',
            'x_delivered_at': self.actual_departure or fields.Datetime.now(),
            'x_delivered_latitude': driver.current_latitude or self.latitude or 0.0,
            'x_delivered_longitude': driver.current_longitude or self.longitude or 0.0,
            'x_receiver_name': self.signature_name or self.contact_name or '',
        })
        picking.message_post(body=_(
            'Entregado por %(driver)s en la ruta %(route)s.',
            driver=driver.name or '', route=self.route_id.name or '',
        ))

        auto_validate = self.env['ir.config_parameter'].sudo().get_param(
            'logistics.auto_validate_picking'
        )
        if auto_validate in ('True', 'true', '1') and picking.state not in ('done', 'cancel'):
            try:
                picking.sudo().with_context(skip_backorder=True).button_validate()
            except Exception as error:  # noqa: BLE001 — nunca bloquear al piloto
                _logger.warning(
                    "No se pudo validar la transferencia %s desde la tarea %s: %s",
                    picking.name, self.id, error,
                )
                picking.message_post(body=_(
                    'La entrega se registró desde la ruta, pero la validación '
                    'automática de la transferencia falló: %(error)s. '
                    'Valídela manualmente.', error=error,
                ))

    def _sync_delivery_document_failed(self, reason):
        """Refleja en la orden de entrega que el piloto no pudo entregar."""
        self.ensure_one()
        picking = self.stock_picking_id
        if not picking:
            return
        picking = picking.sudo()
        picking.write({
            'x_logistics_task_id': self.id,
            'x_logistics_route_id': self.route_id.id,
            'x_delivery_status': 'failed',
        })
        picking.message_post(body=_(
            'Entrega no realizada en la ruta %(route)s. Motivo: %(reason)s',
            route=self.route_id.name or '', reason=reason or _('sin especificar'),
        ))

    def action_mark_failed(self, reason=''):
        """Marcar tarea como fallida."""
        self.ensure_one()
        self.write({
            'state': 'failed',
            'failure_reason': reason,
            'actual_departure': fields.Datetime.now(),
        })
        self._sync_delivery_document_failed(reason)
        self._avisar_a_ventas_y_crm(entregado=False, motivo=reason)

    # ── Aviso al pedido de venta y a la oportunidad del CRM ───────────────────

    def _avisar_a_ventas_y_crm(self, entregado, motivo=''):
        """Avisa el resultado de la entrega donde lo va a ver Ventas.

        La constancia ya queda en la orden de entrega, pero quien atiende al
        cliente trabaja en el pedido de venta y en la oportunidad del CRM.
        Este método publica el mismo aviso en los dos, y se lo notifica al
        vendedor responsable para que no tenga que ir a buscarlo.

        Se ejecuta con `sudo()` porque quien lo dispara es el piloto, que no
        tiene permisos sobre ventas ni sobre el CRM. Cualquier problema al
        avisar se registra en el log y se traga: el piloto ya hizo su
        trabajo en campo y no puede quedar bloqueado por esto.
        """
        self.ensure_one()
        pedido = self._pedido_de_esta_parada()
        if not pedido:
            return

        try:
            cuerpo = self._cuerpo_aviso_entrega(entregado, motivo)
            destinatarios = self._destinatarios_aviso(pedido)

            pedido.message_post(
                body=cuerpo,
                subject=(_('Entrega realizada') if entregado
                         else _('Entrega no realizada')),
                partner_ids=destinatarios,
                # `mt_note` en vez de `mt_comment`: el subtipo nota es
                # INTERNO. Notifica igual al vendedor que se le nombra en
                # `partner_ids`, pero nunca sale hacia un seguidor externo.
                # Con `mt_comment`, si el cliente quedó como seguidor del
                # pedido —cosa que pasa al enviarle la cotización por
                # correo— le habría llegado el nombre del piloto, la placa
                # del vehículo y el número de ruta.
                subtype_xmlid='mail.mt_note',
            )

            # `opportunity_id` lo aporta el puente sale_crm. Si esta base no
            # lo tiene, el aviso al pedido igual se hizo.
            oportunidad = False
            if 'opportunity_id' in pedido._fields:
                oportunidad = pedido.opportunity_id
            if oportunidad:
                oportunidad.sudo().message_post(
                    body=cuerpo,
                    subject=(_('Entrega realizada') if entregado
                             else _('Entrega no realizada')),
                    partner_ids=destinatarios,
                    subtype_xmlid='mail.mt_note',
                )
        except Exception as error:  # noqa: BLE001 — nunca bloquear al piloto
            _logger.warning(
                "No se pudo avisar a Ventas/CRM desde la parada %s: %s",
                self.id, error,
            )

    def _pedido_de_esta_parada(self):
        """El pedido de venta de esta parada, venga por donde venga.

        Lo normal es que la parada se haya creado con el asistente «Crear
        ruta desde entregas», que ya la deja ligada al pedido. Pero si
        alguien armó la ruta a mano y solo puso la transferencia, el enlace
        al pedido queda vacío y antes el aviso no salía. Aquí se recupera
        desde la transferencia.
        """
        self.ensure_one()
        if self.sale_order_id:
            return self.sale_order_id.sudo()
        picking = self.stock_picking_id
        if picking and 'sale_id' in picking._fields:
            pedido = picking.sudo().sale_id
            if pedido:
                return pedido
        return self.env['sale.order']

    def _destinatarios_aviso(self, pedido):
        """A quién se le avisa.

        Primero el vendedor asignado. Si el pedido no tiene vendedor —pasa
        cuando se crea desde bodega o por importación—, se le avisa a quien
        creó el documento, para que el aviso nunca se quede sin dueño.
        """
        destinatarios = self.env['res.partner']
        vendedor = pedido.user_id
        if vendedor and vendedor.partner_id:
            destinatarios |= vendedor.partner_id
        creador = pedido.create_uid
        if creador and creador.partner_id and not creador._is_public():
            destinatarios |= creador.partner_id
        return destinatarios.ids

    def _cuerpo_aviso_entrega(self, entregado, motivo=''):
        """Arma el texto del aviso con los datos de la entrega real."""
        self.ensure_one()
        piloto = self.route_id.driver_id
        vehiculo = self.route_id.vehicle_id
        cuando = self.actual_departure or fields.Datetime.now()
        cuando_txt = fields.Datetime.context_timestamp(self, cuando).strftime(
            '%d/%m/%Y %H:%M'
        )

        filas = [
            (_('Cliente'), self.partner_id.display_name or self.name or ''),
            (_('Piloto'), piloto.name or ''),
            (_('Vehículo'), vehiculo.display_name or ''),
            (_('Ruta'), self.route_id.name or ''),
        ]

        if entregado:
            titulo = _('✅ Entrega realizada')
            filas.append((_('Entregado el'), cuando_txt))
            if self.signature_name:
                filas.append((_('Recibió'), self.signature_name))
            if self.stock_picking_id:
                filas.append((_('Transferencia'), self.stock_picking_id.name))
        else:
            titulo = _('❌ Entrega no realizada')
            filas.append((_('Reportado el'), cuando_txt))
            filas.append((_('Motivo'), motivo or _('sin especificar')))

        lineas = ''.join(
            Markup('<li><b>%s:</b> %s</li>') % (etiqueta, valor)
            for etiqueta, valor in filas if valor
        )
        cuerpo = Markup('<p><b>%s</b></p><ul>%s</ul>') % (titulo, Markup(lineas))

        # Enlace al punto exacto donde se marcó la entrega.
        if entregado and piloto.current_latitude and piloto.current_longitude:
            url = (
                'https://www.google.com/maps?q='
                f'{piloto.current_latitude},{piloto.current_longitude}'
            )
            cuerpo += Markup(
                '<p><a href="%s" target="_blank">%s</a></p>'
            ) % (url, _('Ver en el mapa dónde se entregó'))

        return cuerpo

    def action_navigate_waze(self):
        """Abre Waze con las coordenadas de esta parada."""
        self.ensure_one()
        url = f"https://waze.com/ul?ll={self.latitude},{self.longitude}&navigate=yes&q={self.name}"
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    def action_navigate_google_maps(self):
        """Abre Google Maps con navegación a esta parada."""
        self.ensure_one()
        url = (
            f"https://www.google.com/maps/dir/?api=1"
            f"&destination={self.latitude},{self.longitude}"
            f"&travelmode=driving&dir_action=navigate"
        )
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}
