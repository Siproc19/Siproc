# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

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
        self.env['bus.bus']._sendone(
            f'logistics_task_{self.route_id.id}',
            'task_completed',
            {'task_id': self.id, 'task_name': self.name}
        )

    def action_mark_failed(self, reason=''):
        """Marcar tarea como fallida."""
        self.ensure_one()
        self.write({
            'state': 'failed',
            'failure_reason': reason,
            'actual_departure': fields.Datetime.now(),
        })

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
