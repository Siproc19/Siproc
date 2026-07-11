# -*- coding: utf-8 -*-
import math
from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class VisitVisit(models.Model):
    _name = 'visit.visit'
    _description = 'Visita Comercial'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scheduled_date desc, id desc'

    name = fields.Char(
        string='Numero de Visita',
        readonly=True,
        copy=False,
        default=lambda self: _('Nueva Visita'),
    )
    state = fields.Selection(
        selection=[
            ('draft',      'Programada'),
            ('en_route',   'En Ruta'),
            ('in_process', 'En Proceso'),
            ('done',       'Finalizada'),
            ('cancelled',  'Cancelada'),
        ],
        string='Estado',
        default='draft',
        tracking=True,
        required=True,
    )
    active = fields.Boolean(default=True)
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Importante'), ('2', 'Urgente')],
        default='0',
        string='Prioridad',
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Asesor Responsable',
        required=True,
        tracking=True,
        default=lambda self: self.env.user.employee_id,
        index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        tracking=True,
        index=True,
    )
    contact_id = fields.Many2one(
        'res.partner',
        string='Contacto',
        domain="[('parent_id', '=', partner_id)]",
    )

    visit_type = fields.Selection(
        selection=[
            ('prospect',    'Prospecto'),
            ('follow_up',   'Seguimiento'),
            ('collection',  'Cobro'),
            ('delivery',    'Entrega'),
            ('inspection',  'Inspeccion'),
            ('after_sales', 'Postventa'),
        ],
        string='Tipo de Visita',
        required=True,
        tracking=True,
    )
    visit_objective = fields.Text('Objetivo de la Visita')

    scheduled_date = fields.Date(
        string='Fecha Programada',
        required=True,
        tracking=True,
        index=True,
    )
    scheduled_time = fields.Float(string='Hora Programada')
    real_start_time = fields.Datetime(string='Hora Inicio Real', readonly=True)
    real_end_time = fields.Datetime(string='Hora Fin Real', readonly=True)
    duration = fields.Float(
        string='Duracion (min)',
        compute='_compute_duration',
        store=True,
    )

    # GPS Check-In
    checkin_latitude  = fields.Float('Latitud Check-In',  digits=(10, 7))
    checkin_longitude = fields.Float('Longitud Check-In', digits=(10, 7))
    checkin_address   = fields.Char('Direccion Check-In')
    checkin_accuracy  = fields.Float('Precision GPS Check-In (m)')
    # GPS Check-Out
    checkout_latitude  = fields.Float('Latitud Check-Out',  digits=(10, 7))
    checkout_longitude = fields.Float('Longitud Check-Out', digits=(10, 7))
    checkout_address   = fields.Char('Direccion Check-Out')
    checkout_accuracy  = fields.Float('Precision GPS Check-Out (m)')

    client_latitude = fields.Float(
        related='partner_id.partner_latitude',
        string='Lat. Cliente',
        store=True,
    )
    client_longitude = fields.Float(
        related='partner_id.partner_longitude',
        string='Long. Cliente',
        store=True,
    )
    client_address = fields.Char(
        related='partner_id.street',
        string='Direccion Cliente',
    )

    gps_distance = fields.Float(
        string='Distancia GPS (m)',
        compute='_compute_gps_distance',
        store=True,
    )
    gps_valid = fields.Boolean(
        string='GPS Valido',
        compute='_compute_gps_distance',
        store=True,
        tracking=True,
    )
    gps_tolerance = fields.Float(
        string='Tolerancia GPS (m)',
        default=200.0,
    )

    vehicle_config_id = fields.Many2one(
        'visit.vehicle.config',
        string='Vehiculo',
        tracking=True,
    )
    km_initial  = fields.Float('KM Inicial',  digits=(10, 1))
    km_final    = fields.Float('KM Final',    digits=(10, 1))
    km_traveled = fields.Float(
        'KM Recorridos',
        compute='_compute_km',
        store=True,
        digits=(10, 1),
    )
    fuel_consumption = fields.Float(
        'Consumo Combustible',
        compute='_compute_fuel',
        store=True,
        digits=(10, 2),
    )
    fuel_cost = fields.Float(
        'Costo Estimado Combustible',
        compute='_compute_fuel',
        store=True,
        digits=(10, 0),
    )

    crm_lead_id   = fields.Many2one('crm.lead',   string='Oportunidad CRM')
    sale_order_id = fields.Many2one('sale.order', string='Cotizacion')
    route_line_id = fields.Many2one('visit.route.line', string='Linea de Ruta')

    closing_notes = fields.Text('Comentarios de Cierre')
    result = fields.Selection(
        [
            ('positive',   'Positivo'),
            ('neutral',    'Neutral'),
            ('negative',   'Negativo'),
            ('reschedule', 'Reprogramar'),
        ],
        string='Resultado',
        tracking=True,
    )
    next_action    = fields.Text('Proxima Accion')
    signature      = fields.Binary('Firma del Cliente')
    signature_name = fields.Char('Nombre del Firmante')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'visit_visit_attachment_rel',
        'visit_id',
        'attachment_id',
        string='Adjuntos',
    )

    checkin_ids = fields.One2many(
        'visit.checkin',
        'visit_id',
        string='Registro GPS',
    )
    checkin_count = fields.Integer(
        compute='_compute_checkin_count',
        string='Registros GPS',
    )

    # ── COMPUTES ─────────────────────────────────────────────
    @api.depends('real_start_time', 'real_end_time')
    def _compute_duration(self):
        for rec in self:
            if rec.real_start_time and rec.real_end_time:
                delta = rec.real_end_time - rec.real_start_time
                rec.duration = delta.total_seconds() / 60.0
            else:
                rec.duration = 0.0

    @api.depends('checkin_latitude', 'checkin_longitude',
                 'client_latitude', 'client_longitude', 'gps_tolerance')
    def _compute_gps_distance(self):
        for rec in self:
            if all([rec.checkin_latitude, rec.checkin_longitude,
                    rec.client_latitude, rec.client_longitude]):
                dist = self._haversine(
                    rec.checkin_latitude, rec.checkin_longitude,
                    rec.client_latitude, rec.client_longitude)
                rec.gps_distance = dist
                rec.gps_valid = dist <= (rec.gps_tolerance or 200.0)
            else:
                rec.gps_distance = 0.0
                rec.gps_valid = False

    @api.depends('km_initial', 'km_final')
    def _compute_km(self):
        for rec in self:
            if rec.km_final and rec.km_initial:
                rec.km_traveled = max(rec.km_final - rec.km_initial, 0.0)
            else:
                rec.km_traveled = 0.0

    @api.depends('km_traveled', 'vehicle_config_id',
                 'vehicle_config_id.km_per_unit',
                 'vehicle_config_id.fuel_price')
    def _compute_fuel(self):
        for rec in self:
            cfg = rec.vehicle_config_id
            if cfg and rec.km_traveled and cfg.km_per_unit:
                consumption = rec.km_traveled / cfg.km_per_unit
                rec.fuel_consumption = consumption
                rec.fuel_cost = consumption * (cfg.fuel_price or 0.0)
            else:
                rec.fuel_consumption = 0.0
                rec.fuel_cost = 0.0

    def _compute_checkin_count(self):
        for rec in self:
            rec.checkin_count = len(rec.checkin_ids)

    # ── CONSTRAINTS ──────────────────────────────────────────
    @api.constrains('km_initial', 'km_final')
    def _check_km(self):
        for rec in self:
            if rec.km_final and rec.km_initial and rec.km_final < rec.km_initial:
                raise ValidationError(
                    _('El KM final no puede ser menor al KM inicial.'))

    # ── ACCIONES ─────────────────────────────────────────────
    def action_start_route(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se pueden iniciar visitas Programadas.'))
        self.write({'state': 'en_route'})
        self.message_post(body=_('El asesor ha iniciado la ruta.'))
        return True

    def action_checkin(self):
        self.ensure_one()
        if self.state != 'en_route':
            raise UserError(_('Debe iniciar la ruta antes del Check-In.'))
        self.write({
            'state': 'in_process',
            'real_start_time': fields.Datetime.now(),
        })
        self.env['visit.checkin'].create({
            'visit_id': self.id,
            'checkin_type': 'in',
            'latitude': self.checkin_latitude,
            'longitude': self.checkin_longitude,
            'address': self.checkin_address,
            'accuracy_m': self.checkin_accuracy,
        })
        self.message_post(body=_('Check-In registrado.'))
        return True

    def action_checkout(self):
        self.ensure_one()
        if self.state != 'in_process':
            raise UserError(_('Solo se pueden finalizar visitas En Proceso.'))
        if not self.closing_notes:
            raise UserError(
                _('Debe ingresar comentarios de cierre antes de finalizar.'))
        self.write({
            'state': 'done',
            'real_end_time': fields.Datetime.now(),
        })
        self.env['visit.checkin'].create({
            'visit_id': self.id,
            'checkin_type': 'out',
            'latitude': self.checkout_latitude,
            'longitude': self.checkout_longitude,
            'address': self.checkout_address,
            'accuracy_m': self.checkout_accuracy,
        })
        self.message_post(body=_('Visita finalizada.'))
        self._post_visit_automation()
        return True

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_('No se puede cancelar una visita finalizada.'))
        self.write({'state': 'cancelled'})
        return True

    def action_reset_draft(self):
        self.ensure_one()
        self.write({'state': 'draft'})
        return True

    def action_create_opportunity(self):
        self.ensure_one()
        lead = self.env['crm.lead'].create({
            'name': _('Oportunidad - %s (%s)') % (self.partner_id.name, self.name),
            'partner_id': self.partner_id.id,
            'user_id': self.employee_id.user_id.id or self.env.uid,
            'description': self.closing_notes or '',
            'type': 'opportunity',
        })
        self.crm_lead_id = lead.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'res_id': lead.id,
            'view_mode': 'form',
        }

    def action_create_quotation(self):
        self.ensure_one()
        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'user_id': self.employee_id.user_id.id or self.env.uid,
            'origin': self.name,
        })
        self.sale_order_id = order.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': order.id,
            'view_mode': 'form',
        }

    def action_open_google_maps(self):
        self.ensure_one()
        if not self.client_latitude or not self.client_longitude:
            raise UserError(_('El cliente no tiene coordenadas GPS configuradas.'))
        url = 'https://www.google.com/maps/dir/?api=1&destination=%s,%s' % (
            self.client_latitude, self.client_longitude)
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    def action_open_waze(self):
        self.ensure_one()
        if not self.client_latitude or not self.client_longitude:
            raise UserError(_('El cliente no tiene coordenadas GPS configuradas.'))
        url = 'https://waze.com/ul?ll=%s,%s&navigate=yes' % (
            self.client_latitude, self.client_longitude)
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    def action_reschedule(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reprogramar Visita'),
            'res_model': 'visit.reschedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_visit_id': self.id},
        }

    # ── CRON ─────────────────────────────────────────────────
    @api.model
    def _cron_alert_missing_checkin(self):
        limit = fields.Datetime.now() - timedelta(hours=1)
        today = fields.Date.today()
        visits = self.search([
            ('state', '=', 'draft'),
            ('scheduled_date', '=', today),
            ('create_date', '<=', limit),
        ])
        for visit in visits:
            visit.message_post(
                body=_('Alerta: el asesor %s no ha iniciado la visita con %s.')
                % (visit.employee_id.name, visit.partner_id.name))

    @api.model
    def _cron_alert_no_checkout(self):
        yesterday = fields.Date.today() - timedelta(days=1)
        visits = self.search([
            ('state', 'in', ['en_route', 'in_process']),
            ('scheduled_date', '=', yesterday),
        ])
        for visit in visits:
            visit.message_post(
                body=_('Alerta: la visita %s no fue cerrada.') % visit.name)

    # ── UTILS ────────────────────────────────────────────────
    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2) ** 2
             + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _post_visit_automation(self):
        self.activity_schedule(
            act_type_xmlid='mail.mail_activity_data_todo',
            summary=_('Seguimiento post-visita: %s') % self.partner_id.name,
            date_deadline=fields.Date.today() + timedelta(days=2),
            user_id=self.employee_id.user_id.id or self.env.uid,
        )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name', _('Nueva Visita')) == _('Nueva Visita'):
                vals['name'] = seq.next_by_code('visit.visit') or _('Nueva Visita')
        return super().create(vals_list)
