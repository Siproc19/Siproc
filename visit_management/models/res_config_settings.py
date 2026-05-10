# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Tolerancia GPS global
    visit_gps_tolerance = fields.Float(
        string='Tolerancia GPS por Defecto (m)',
        default=200.0,
        config_parameter='visit_management.gps_tolerance',
        help='Distancia máxima en metros permitida para validar un Check-In GPS.',
    )

    # Proveedor de mapas
    visit_map_provider = fields.Selection(
        selection=[
            ('google',        'Google Maps'),
            ('openstreetmap', 'OpenStreetMap'),
            ('mapbox',        'MapBox'),
        ],
        string='Proveedor de Mapas',
        default='google',
        config_parameter='visit_management.map_provider',
    )

    # API Keys
    visit_google_maps_key = fields.Char(
        string='Google Maps API Key',
        config_parameter='visit_management.google_maps_key',
    )
    visit_mapbox_key = fields.Char(
        string='MapBox API Key',
        config_parameter='visit_management.mapbox_key',
    )

    # Alertas
    visit_alert_hours = fields.Integer(
        string='Horas sin Check-In para Alerta',
        default=1,
        config_parameter='visit_management.alert_hours',
        help='Número de horas después de la hora programada para generar alerta de falta de Check-In.',
    )

    # Firma obligatoria
    visit_require_signature = fields.Boolean(
        string='Requerir Firma del Cliente',
        config_parameter='visit_management.require_signature',
        default=False,
    )

    # Fotos obligatorias
    visit_require_photo = fields.Boolean(
        string='Requerir Foto como Evidencia',
        config_parameter='visit_management.require_photo',
        default=False,
    )
