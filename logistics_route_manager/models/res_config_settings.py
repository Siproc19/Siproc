# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    """Configuración del módulo de logística en Ajustes > Logística."""
    _inherit = 'res.config.settings'

    logistics_google_maps_api_key = fields.Char(
        string='API Key de Google Maps',
        config_parameter='logistics.google_maps_api_key',
        help='Obtenga su API Key en https://console.cloud.google.com/',
    )
    logistics_gps_interval = fields.Integer(
        string='Intervalo de Actualización GPS (segundos)',
        config_parameter='logistics.gps_interval',
        default=15,
        help='Cada cuántos segundos el celular del piloto envía su posición.',
    )
    logistics_geofence_radius = fields.Integer(
        string='Radio de Llegada Automática (metros)',
        config_parameter='logistics.geofence_radius',
        default=50,
        help='Cuando el piloto esté a esta distancia de una parada, se marcará como "Llegó" automáticamente.',
    )
    logistics_auto_optimize = fields.Boolean(
        string='Optimizar Rutas Automáticamente',
        config_parameter='logistics.auto_optimize',
        help='Optimizar el orden de paradas al confirmar la ruta.',
    )
    logistics_notify_manager = fields.Boolean(
        string='Notificar al Jefe cuando el Piloto llega',
        config_parameter='logistics.notify_manager',
        default=True,
    )
    logistics_notify_customer = fields.Boolean(
        string='Notificar al Cliente cuando el Piloto está cerca',
        config_parameter='logistics.notify_customer',
        default=False,
    )
    logistics_default_nav_app = fields.Selection([
        ('waze', 'Waze'),
        ('google_maps', 'Google Maps'),
    ], string='App de Navegación por Defecto',
        config_parameter='logistics.default_nav_app',
        default='waze',
    )
