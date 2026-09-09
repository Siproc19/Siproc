# -*- coding: utf-8 -*-
import logging
import secrets

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class LogisticsDriver(models.Model):
    """Piloto / Conductor logístico con rastreo GPS en tiempo real."""
    _name = 'logistics.driver'
    _description = 'Piloto Logístico'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(
        string='Nombre',
        related='employee_id.name',
        store=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='restrict',
        tracking=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Usuario Odoo',
        help='Opcional. Un piloto puede trabajar solo con su enlace '
             'personal, sin usuario de Odoo y sin consumir licencia.',
    )
    # ── Acceso sin usuario de Odoo ───────────────────────────────────────
    #
    # Un piloto no necesita usuario de Odoo. Este token lo identifica: con
    # él entra a su app de rutas, marca entregas y manda posición, sin
    # iniciar sesión y sin consumir una licencia.
    #
    # Es una credencial al portador: quien tenga el enlace puede actuar
    # como ese piloto. Por eso es largo, es secreto, solo lo ve el Jefe de
    # Logística, y se puede regenerar en cualquier momento — al hacerlo,
    # el enlace anterior deja de servir al instante.
    gps_token = fields.Char(
        string='Token del Piloto', copy=False, readonly=True, index=True,
        groups='logistics_route_manager.group_logistics_manager',
        help='Clave privada de este piloto. Si se filtra, regenérela.',
    )
    app_url = fields.Char(
        string='Enlace de su app', compute='_compute_gps_push_url',
        groups='logistics_route_manager.group_logistics_manager',
        help='Enlace personal del piloto. Se le manda por WhatsApp una '
             'sola vez; él lo agrega a la pantalla de inicio.',
    )
    gps_push_url = fields.Char(
        string='Dirección para el rastreador', compute='_compute_gps_push_url',
        groups='logistics_route_manager.group_logistics_manager',
        help='Péguela tal cual en la app de rastreo en segundo plano.',
    )
    battery_level = fields.Integer(
        string='Batería del Teléfono (%)', readonly=True,
        help='Último nivel de batería informado por el rastreador. '
             'Un teléfono descargado es la causa más común de «sin señal».',
    )

    license_number = fields.Char(string='Número de Licencia', tracking=True)
    license_expiry = fields.Date(string='Vencimiento de Licencia', tracking=True)
    license_type = fields.Selection([
        ('a', 'Tipo A'),
        ('b', 'Tipo B'),
        ('c', 'Tipo C'),
        ('e', 'Tipo E'),
    ], string='Tipo de Licencia')

    # ── Token de rastreo ─────────────────────────────────────────────────

    @staticmethod
    def _nuevo_token():
        """Token largo y aleatorio, apto para ir en una URL."""
        return secrets.token_urlsafe(32)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('gps_token', self._nuevo_token())
        return super().create(vals_list)

    def action_regenerar_token_gps(self):
        """Cambia el token. El rastreador viejo deja de funcionar al instante."""
        for rec in self:
            rec.sudo().gps_token = self._nuevo_token()
            rec.message_post(body=_(
                'Se regeneró el token de rastreo. Hay que volver a '
                'configurar la app del celular con la dirección nueva.'
            ))
        return True

    @api.depends('gps_token')
    def _compute_gps_push_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for rec in self:
            token = rec.sudo().gps_token
            if token:
                rec.app_url = f'{base}/logistics/driver/app?token={token}'
                # Marcadores de GPSLogger: la app los sustituye por los
                # valores reales de cada lectura.
                rec.gps_push_url = (
                    f'{base}/logistics/gps/push'
                    f'?token={token}'
                    '&lat=%LAT&lon=%LON&speed=%SPD&heading=%DIR'
                    '&acc=%ACC&batt=%BATT'
                )
            else:
                rec.app_url = False
                rec.gps_push_url = False

    phone = fields.Char(
        string='Teléfono (GPS)',
        help='Número de teléfono del celular que usará para rastreo GPS',
        tracking=True,
    )
    preferred_nav_app = fields.Selection([
        ('waze', 'Waze'),
        ('google_maps', 'Google Maps'),
    ], string='App de Navegación Preferida', default='waze')

    # GPS en tiempo real
    current_latitude = fields.Float(
        string='Latitud Actual',
        digits=(10, 7),
        readonly=True,
    )
    current_longitude = fields.Float(
        string='Longitud Actual',
        digits=(10, 7),
        readonly=True,
    )
    last_gps_update = fields.Datetime(
        string='Última Actualización GPS',
        readonly=True,
    )
    current_speed = fields.Float(
        string='Velocidad Actual (km/h)',
        readonly=True,
    )
    current_heading = fields.Float(
        string='Dirección (grados)',
        readonly=True,
    )
    is_online = fields.Boolean(
        string='En Línea',
        compute='_compute_is_online',
        help='El piloto envió su posición en los últimos 2 minutos',
    )

    current_route_id = fields.Many2one(
        'logistics.route',
        string='Ruta Actual',
        compute='_compute_current_route',
    )
    is_active = fields.Boolean(string='Activo', default=True)
    image = fields.Binary(
        string='Foto',
        related='employee_id.image_1920',
    )

    route_ids = fields.One2many(
        'logistics.route', 'driver_id',
        string='Rutas Asignadas',
    )
    gps_history_ids = fields.One2many(
        'logistics.gps.history',
        'driver_id',
        string='Historial GPS',
    )

    @api.depends('last_gps_update')
    def _compute_is_online(self):
        """El piloto está en línea si envió GPS en los últimos 2 minutos."""
        now = fields.Datetime.now()
        for rec in self:
            if rec.last_gps_update:
                diff = (now - rec.last_gps_update).total_seconds()
                rec.is_online = diff < 120
            else:
                rec.is_online = False

    @api.depends('route_ids', 'route_ids.state')
    def _compute_current_route(self):
        for rec in self:
            active = rec.route_ids.filtered(lambda r: r.state == 'in_progress')
            rec.current_route_id = active[0] if active else False

    def update_gps_position(self, latitude, longitude, speed=0.0, heading=0.0):
        """
        Actualiza la posición GPS del piloto en tiempo real.
        Llamado desde el controller del celular del piloto.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        self.write({
            'current_latitude': latitude,
            'current_longitude': longitude,
            'current_speed': speed,
            'current_heading': heading,
            'last_gps_update': now,
        })
        # Guardar en historial
        self.env['logistics.gps.history'].create({
            'driver_id': self.id,
            'route_id': self.current_route_id.id if self.current_route_id else False,
            'latitude': latitude,
            'longitude': longitude,
            'speed': speed,
            'heading': heading,
            'timestamp': now,
        })
        # Notificar via Odoo Bus para actualizar mapa del jefe en tiempo real
        self.env['bus.bus']._sendone(
            f'logistics_gps_{self.id}',
            'gps_update',
            {
                'driver_id': self.id,
                'driver_name': self.name,
                'latitude': latitude,
                'longitude': longitude,
                'speed': speed,
                'heading': heading,
                'timestamp': now.isoformat(),
                'route_id': self.current_route_id.id if self.current_route_id else False,
            }
        )
        _logger.info(f"GPS actualizado para piloto {self.name}: {latitude}, {longitude}")
        return True

    def get_current_position(self):
        """Retorna la posición actual del piloto."""
        self.ensure_one()
        return {
            'latitude': self.current_latitude,
            'longitude': self.current_longitude,
            'speed': self.current_speed,
            'heading': self.current_heading,
            'last_update': self.last_gps_update.isoformat() if self.last_gps_update else None,
            'is_online': self.is_online,
        }


class LogisticsGpsHistory(models.Model):
    """Historial de posiciones GPS del piloto durante una ruta."""
    _name = 'logistics.gps.history'
    _description = 'Historial GPS del Piloto'
    _order = 'timestamp desc'
    _rec_name = 'timestamp'

    driver_id = fields.Many2one('logistics.driver', string='Piloto', required=True, ondelete='cascade')
    route_id = fields.Many2one('logistics.route', string='Ruta', ondelete='set null')
    latitude = fields.Float(string='Latitud', digits=(10, 7))
    longitude = fields.Float(string='Longitud', digits=(10, 7))
    speed = fields.Float(string='Velocidad (km/h)')
    heading = fields.Float(string='Dirección (grados)')
    timestamp = fields.Datetime(string='Fecha/Hora', default=fields.Datetime.now)
