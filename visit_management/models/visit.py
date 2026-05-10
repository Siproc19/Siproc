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
    _rec_name = 'name'

    # ─────────────────────────────────────────────────────────────
    # IDENTIFICACIÓN
    # ─────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Número de Visita',
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
    color = fields.Integer('Color Index')
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Importante'), ('2', 'Urgente')],
        default='0',
    )

    # ─────────────────────────────────────────────────────────────
    # PERSONAS
    # ─────────────────────────────────────────────────────────────
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Asesor Responsable',
        required=True,
        tracking=True,
        default=lambda self: self.env.user.employee_id,
        index=True,
    )
    user_id = fields.Many2one(
        related='employee_id.user_id',
        string='Usuario',
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Cliente',
        required=True,
        tracking=True,
        index=True,
    )
    contact_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contacto',
        domain="[('parent_id', '=', partner_id)]",
    )

    # ─────────────────────────────────────────────────────────────
    # TIPO Y CATEGORÍA
    # ─────────────────────────────────────────────────────────────
    visit_type = fields.Selection(
        selection=[
            ('prospect',    'Prospecto'),
            ('follow_up',   'Seguimiento'),
            ('collection',  'Cobro'),
            ('delivery',    'Entrega'),
            ('inspection',  'Inspección'),
            ('after_sales', 'Postventa'),
        ],
        string='Tipo de Visita',
        required=True,
        tracking=True,
    )
    visit_objective = fields.Text('Objetivo de la Visita')

    # ─────────────────────────────────────────────────────────────
    # TIEMPOS
    # ─────────────────────────────────────────────────────────────
    scheduled_date = fields.Date(
        string='Fecha Programada',
        required=True,
        tracking=True,
        index=True,
    )
    scheduled_time = fields.Float(
        string='Hora Programada',
        tracking=True,
    )
    real_start_time = fields.Datetime(
        string='Hora Inicio Real',
        readonly=True,
        tracking=True,
    )
    real_end_time = fields.Datetime(
        string='Hora Fin Real',
        readonly=True,
        tracking=True,
    )
    duration = fields.Float(
        string='Duración (min)',
        compute='_compute_duration',
        store=True,
    )

    # ─────────────────────────────────────────────────────────────
    # GEOLOCALIZACIÓN — CHECK-IN
    # ─────────────────────────────────────────────────────────────
    checkin_latitude  = fields.Float('Latitud Check-In',  digits=(10, 7))
    checkin_longitude = fields.Float('Longitud Check-In', digits=(10, 7))
    checkin_address   = fields.Char('Dirección Check-In')
    checkin_accuracy  = fields.Float('Precisión GPS Check-In (m)')

    # GEOLOCALIZACIÓN — CHECK-OUT
    checkout_latitude  = fields.Float('Latitud Check-Out',  digits=(10, 7))
    checkout_longitude = fields.Float('Longitud Check-Out', digits=(10, 7))
    checkout_address   = fields.Char('Dirección Check-Out')
    checkout_accuracy  = fields.Float('Precisión GPS Check-Out (m)')

    # Coordenadas del cliente (desde res.partner)
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
        string='Dirección Cliente',
    )

    # Validación GPS
    gps_distance = fields.Float(
        string='Distancia GPS (m)',
        compute='_compute_gps_distance',
        store=True,
        help='Distancia en metros entre la ubicación del asesor y el cliente.',
    )
    gps_valid = fields.Boolean(
        string='GPS Válido',
        compute='_compute_gps_distance',
        store=True,
        tracking=True,
    )
    gps_tolerance = fields.Float(
        string='Tolerancia GPS (m)',
        default=200.0,
        help='Distancia máxima permitida en metros para validar la visita.',
    )

    # ─────────────────────────────────────────────────────────────
    # KILOMETRAJE Y COMBUSTIBLE
    # ─────────────────────────────────────────────────────────────
    vehicle_config_id = fields.Many2one(
        comodel_name='visit.vehicle.config',
        string='Vehículo',
        tracking=True,
    )
    km_initial  = fields.Float('KM Inicial',  digits=(10, 1))
    km_final    = fields.Float('KM Final',    digits=(10, 1))
    km_traveled = fields.Float(
        string='KM Recorridos',
        compute='_compute_km',
        store=True,
        digits=(10, 1),
    )
    fuel_consumption = fields.Float(
        string='Consumo Combustible (L/Gal)',
        compute='_compute_fuel',
        store=True,
        digits=(10, 2),
    )
    fuel_cost = fields.Float(
        string='Costo Estimado Combustible',
        compute='_compute_fuel',
        store=True,
        digits=(10, 0),
    )
    currency_id = fields.Many2one(
        related='vehicle_config_id.currency_id',
        string='Moneda',
    )

    # ─────────────────────────────────────────────────────────────
    # RELACIONES CRM / VENTAS
    # ─────────────────────────────────────────────────────────────
    crm_lead_id   = fields.Many2one('crm.lead',   string='Oportunidad CRM')
    sale_order_id = fields.Many2one('sale.order', string='Cotización/Pedido')
    route_line_id = fields.Many2one('visit.route.line', string='Línea de Ruta')

    # ─────────────────────────────────────────────────────────────
    # EVIDENCIAS Y CIERRE
    # ─────────────────────────────────────────────────────────────
    closing_notes  = fields.Text('Comentarios de Cierre')
    result         = fields.Selection(
        [
            ('positive',  'Positivo'),
            ('neutral',   'Neutral'),
            ('negative',  'Negativo'),
            ('reschedule','Reprogramar'),
        ],
        string='Resultado',
        tracking=True,
    )
    next_action    = fields.Text('Próxima Acción')
    signature      = fields.Binary('Firma del Cliente')
    signature_name = fields.Char('Nombre del Firmante')

    # ─────────────────────────────────────────────────────────────
    # CHECKINS LOG
    # ─────────────────────────────────────────────────────────────
    checkin_ids = fields.One2many(
        comodel_name='visit.checkin',
        inverse_name='visit_id',
        string='Registro GPS',
    )
    checkin_count = fields.Integer(
        compute='_compute_checkin_count',
        string='# Registros GPS',
    )

    # ─────────────────────────────────────────────────────────────
    # COMPUTES
    # ─────────────────────────────────────────────────────────────
    @api.depends('real_start_time', 'real_end_time')
    def _compute_duration(self):
        for rec in self:
            if rec.real_start_time and rec.real_end_time:
                delta = rec.real_end_time - rec.real_start_time
                rec.duration = delta.total_seconds() / 60.0
            else:
                rec.duration = 0.0

    @api.depends(
        'checkin_latitude', 'checkin_longitude',
        'client_latitude',  'client_longitude',
        'gps_tolerance',
    )
    def _compute_gps_distance(self):
        for rec in self:
            if all([
                rec.checkin_latitude,  rec.checkin_longitude,
                rec.client_latitude,   rec.client_longitude,
            ]):
                dist = self._haversine(
                    rec.checkin_latitude,  rec.checkin_longitude,
                    rec.client_latitude,   rec.client_longitude,
                )
                rec.gps_distance = dist
                rec.gps_valid    = dist <= (rec.gps_tolerance or 200.0)
            else:
                rec.gps_distance = 0.0
                rec.gps_valid    = False

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
                consumption       = rec.km_traveled / cfg.km_per_unit
                rec.fuel_consumption = consumption
                rec.fuel_cost        = consumption * (cfg.fuel_price or 0.0)
            else:
                rec.fuel_consumption = 0.0
                rec.fuel_cost        = 0.0

    @api.depends('checkin_ids')
    def _compute_checkin_count(self):
        for rec in self:
            rec.checkin_count = len(rec.checkin_ids)

    # ─────────────────────────────────────────────────────────────
    # CONSTRAINTS
    # ─────────────────────────────────────────────────────────────
    @api.constrains('km_initial', 'km_final')
    def _check_km(self):
        for rec in self:
            if rec.km_final and rec.km_initial and rec.km_final < rec.km_initial:
                raise ValidationError(
                    _('El KM final no puede ser menor al KM inicial.')
                )

    @api.constrains('real_start_time', 'real_end_time')
    def _check_times(self):
        for rec in self:
            if rec.real_start_time and rec.real_end_time:
                if rec.real_end_time < rec.real_start_time:
                    raise ValidationError(
                        _('La hora de fin no puede ser anterior a la hora de inicio.')
                    )

    # ─────────────────────────────────────────────────────────────
    # ACCIONES DE ESTADO
    # ─────────────────────────────────────────────────────────────
    def action_start_route(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Solo se pueden iniciar visitas en estado Programada.'))
        self.write({'state': 'en_route'})
        self._send_notification('en_route')
        return True

    def action_checkin(self):
        self.ensure_one()
        if self.state != 'en_route':
            raise UserError(_('Debe iniciar la ruta antes de hacer Check-In.'))
        self.write({
            'state':          'in_process',
            'real_start_time': fields.Datetime.now(),
        })
        # Registrar en log de checkins
        self.env['visit.checkin'].create({
            'visit_id':     self.id,
            'checkin_type': 'in',
            'latitude':     self.checkin_latitude,
            'longitude':    self.checkin_longitude,
            'address':      self.checkin_address,
            'accuracy_m':   self.checkin_accuracy,
        })
        self._send_notification('checkin')
        return True

    def action_checkout(self):
        self.ensure_one()
        if self.state != 'in_process':
            raise UserError(_('Solo se pueden finalizar visitas En Proceso.'))
        if not self.closing_notes:
            raise UserError(
                _('Debe ingresar comentarios de cierre antes de finalizar la visita.')
            )
        self.write({
            'state':        'done',
            'real_end_time': fields.Datetime.now(),
        })
        # Registrar en log de checkins
        self.env['visit.checkin'].create({
            'visit_id':     self.id,
            'checkin_type': 'out',
            'latitude':     self.checkout_latitude,
            'longitude':    self.checkout_longitude,
            'address':      self.checkout_address,
            'accuracy_m':   self.checkout_accuracy,
        })
        self._send_notification('checkout')
        self._post_visit_automation()
        return True

    def action_cancel(self):
        self.ensure_one()
        if self.state == 'done':
            raise UserError(_('No se puede cancelar una visita ya finalizada.'))
        self.write({'state': 'cancelled'})
        return True

    def action_reset_draft(self):
        self.ensure_one()
        if self.state not in ('cancelled',):
            raise UserError(_('Solo se pueden reprogramar visitas canceladas.'))
        self.write({'state': 'draft'})
        return True

    # ─────────────────────────────────────────────────────────────
    # ACCIONES CRM / VENTAS
    # ─────────────────────────────────────────────────────────────
    def action_create_opportunity(self):
        self.ensure_one()
        lead_vals = {
            'name':        f'Oportunidad — {self.partner_id.name} ({self.name})',
            'partner_id':  self.partner_id.id,
            'user_id':     self.employee_id.user_id.id,
            'description': self.closing_notes or '',
            'type':        'opportunity',
        }
        lead = self.env['crm.lead'].create(lead_vals)
        self.crm_lead_id = lead.id
        self.message_post(
            body=_('Oportunidad CRM creada: <a href="/odoo/crm/%s">%s</a>') % (lead.id, lead.name)
        )
        return {
            'type':      'ir.actions.act_window',
            'res_model': 'crm.lead',
            'res_id':    lead.id,
            'view_mode': 'form',
            'target':    'current',
        }

    def action_create_quotation(self):
        self.ensure_one()
        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'user_id':    self.employee_id.user_id.id,
            'origin':     self.name,
        })
        self.sale_order_id = order.id
        self.message_post(
            body=_('Cotización creada: <a href="/odoo/sales/%s">%s</a>') % (order.id, order.name)
        )
        return {
            'type':      'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id':    order.id,
            'view_mode': 'form',
            'target':    'current',
        }

    def action_open_google_maps(self):
        self.ensure_one()
        lat = self.client_latitude  or 0.0
        lng = self.client_longitude or 0.0
        if not lat or not lng:
            raise UserError(
                _('El cliente no tiene coordenadas GPS configuradas. '
                  'Configure la ubicación en el formulario del cliente.')
            )
        url = f'https://www.google.com/maps/dir/?api=1&destination={lat},{lng}'
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    def action_open_waze(self):
        self.ensure_one()
        lat = self.client_latitude  or 0.0
        lng = self.client_longitude or 0.0
        if not lat or not lng:
            raise UserError(_('El cliente no tiene coordenadas GPS configuradas.'))
        url = f'https://waze.com/ul?ll={lat},{lng}&navigate=yes'
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    def action_view_checkins(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      _('Registros GPS'),
            'res_model': 'visit.checkin',
            'view_mode': 'list,form',
            'domain':    [('visit_id', '=', self.id)],
            'target':    'new',
        }

    # ─────────────────────────────────────────────────────────────
    # WIZARD REPROGRAMACIÓN
    # ─────────────────────────────────────────────────────────────
    def action_reschedule(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      _('Reprogramar Visita'),
            'res_model': 'visit.reschedule.wizard',
            'view_mode': 'form',
            'target':    'new',
            'context':   {'default_visit_id': self.id},
        }

    # ─────────────────────────────────────────────────────────────
    # CRON JOBS
    # ─────────────────────────────────────────────────────────────
    @api.model
    def _cron_alert_missing_checkin(self):
        """Alerta visitas programadas para hoy sin iniciar después de 1 hora."""
        now   = fields.Datetime.now()
        limit = now - timedelta(hours=1)
        today = fields.Date.today()

        visits = self.search([
            ('state',          '=',  'draft'),
            ('scheduled_date', '=',  today),
            ('create_date',    '<=', limit),
        ])
        for visit in visits:
            supervisor = visit.employee_id.parent_id
            partner_ids = []
            if supervisor and supervisor.user_id:
                partner_ids.append(supervisor.user_id.partner_id.id)

            visit.message_post(
                body=_(
                    '⚠️ <b>Alerta:</b> El asesor <b>%s</b> no ha iniciado '
                    'la visita programada para hoy con el cliente <b>%s</b>.'
                ) % (visit.employee_id.name, visit.partner_id.name),
                partner_ids=partner_ids,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
            # Crear actividad de advertencia
            visit.activity_schedule(
                activity_type_xmlid='mail.mail_activity_data_warning',
                summary=_('Visita sin iniciar — requiere atención'),
                user_id=(supervisor.user_id.id if supervisor and supervisor.user_id
                         else self.env.uid),
            )

    @api.model
    def _cron_alert_no_checkout(self):
        """Alerta visitas en proceso que no cerraron en el día."""
        yesterday = fields.Date.today() - timedelta(days=1)
        visits = self.search([
            ('state',          'in', ['en_route', 'in_process']),
            ('scheduled_date', '=',  yesterday),
        ])
        for visit in visits:
            visit.message_post(
                body=_(
                    '🔴 <b>Alerta:</b> La visita <b>%s</b> del asesor <b>%s</b> '
                    'no fue cerrada. Requiere atención.'
                ) % (visit.name, visit.employee_id.name),
                message_type='notification',
            )

    @api.model
    def _cron_send_daily_reminders(self):
        """Envía recordatorio a asesores con visitas programadas para hoy."""
        today   = fields.Date.today()
        visits  = self.search([
            ('state',          '=', 'draft'),
            ('scheduled_date', '=', today),
        ])
        # Agrupar por asesor
        asesor_visits = {}
        for visit in visits:
            uid = visit.employee_id.user_id
            if uid:
                asesor_visits.setdefault(uid, []).append(visit)

        for user, v_list in asesor_visits.items():
            names = ', '.join(v.partner_id.name for v in v_list)
            # Enviar notificación interna al asesor via partner
            user.partner_id.message_notify(
                subject=_('Recordatorio de visitas para hoy'),
                body=_(
                    '📅 <b>Recordatorio:</b> Tienes <b>%d</b> visita(s) programada(s) para hoy: %s'
                ) % (len(v_list), names),
                partner_ids=[user.partner_id.id],
            )

    # ─────────────────────────────────────────────────────────────
    # UTILITIES PRIVADAS
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        """Calcula distancia en metros entre dos coordenadas GPS."""
        R = 6_371_000  # Radio Tierra en metros
        phi1  = math.radians(lat1)
        phi2  = math.radians(lat2)
        dphi  = math.radians(lat2 - lat1)
        dlam  = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2) ** 2
             + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _send_notification(self, event_type):
        messages = {
            'en_route': '🚗 <b>En Ruta:</b> El asesor ha iniciado el desplazamiento.',
            'checkin':  '📍 <b>Check-In:</b> El asesor llegó al punto de visita.',
            'checkout': '✅ <b>Visita Finalizada:</b> Check-Out registrado correctamente.',
        }
        body = messages.get(event_type, '')
        if body:
            self.message_post(body=body, message_type='notification')

    def _post_visit_automation(self):
        """Acciones automáticas al cerrar una visita exitosa."""
        deadline = fields.Date.today() + timedelta(days=2)
        self.activity_schedule(
            activity_type_xmlid='mail.mail_activity_data_todo',
            summary=_('Seguimiento post-visita: %s') % self.partner_id.name,
            date_deadline=deadline,
            user_id=self.employee_id.user_id.id,
        )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name', _('Nueva Visita')) == _('Nueva Visita'):
                vals['name'] = seq.next_by_code('visit.visit') or _('Nueva Visita')
            # Heredar tolerancia GPS de configuración global
            if 'gps_tolerance' not in vals:
                tolerance = float(
                    self.env['ir.config_parameter'].sudo()
                    .get_param('visit_management.gps_tolerance', 200)
                )
                vals['gps_tolerance'] = tolerance
        return super().create(vals_list)
