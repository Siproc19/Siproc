# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime
import logging

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
        help='Usuario para acceder a la app del piloto',
    )
    license_number = fields.Char(string='Número de Licencia', tracking=True)
    license_expiry = fields.Date(string='Vencimiento de Licencia', tracking=True)
    license_type = fields.Selection([
        ('a', 'Tipo A'),
        ('b', 'Tipo B'),
        ('c', 'Tipo C'),
        ('e', 'Tipo E'),
    ], string='Tipo de Licencia')

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
        now = datetime.now()
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
        now = datetime.now()
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
