# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LogisticsLocation(models.Model):
    """Lugares y puntos frecuentes de logística para marcar en el mapa."""
    _name = 'logistics.location'
    _description = 'Ubicación Logística'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(
        string='Nombre del Lugar',
        required=True,
        tracking=True,
    )
    location_type = fields.Selection([
        ('customer', 'Cliente'),
        ('supplier', 'Proveedor'),
        ('bank', 'Banco'),
        ('office', 'Oficina'),
        ('warehouse', 'Bodega'),
        ('other', 'Otro'),
    ], string='Tipo de Lugar', required=True, default='customer', tracking=True)

    address = fields.Char(string='Dirección Completa', tracking=True)
    latitude = fields.Float(string='Latitud', digits=(10, 7))
    longitude = fields.Float(string='Longitud', digits=(10, 7))
    contact_name = fields.Char(string='Nombre de Contacto')
    contact_phone = fields.Char(string='Teléfono de Contacto')
    notes = fields.Text(string='Notas / Indicaciones')
    color = fields.Integer(string='Color del Marcador', default=0)
    active = fields.Boolean(string='Activo', default=True)

    # Relación con tareas
    task_ids = fields.One2many(
        'logistics.task', 'location_id',
        string='Tareas en este lugar',
    )
    task_count = fields.Integer(
        string='Total de Tareas',
        compute='_compute_task_count',
    )

    @api.depends('task_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)

    def action_open_in_google_maps(self):
        """Abre la ubicación en Google Maps en el navegador."""
        self.ensure_one()
        url = f"https://www.google.com/maps?q={self.latitude},{self.longitude}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def action_open_in_waze(self):
        """Abre la ubicación en Waze en el navegador."""
        self.ensure_one()
        url = f"https://waze.com/ul?ll={self.latitude},{self.longitude}&navigate=yes"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        """Valida que las coordenadas sean válidas."""
        for rec in self:
            if rec.latitude and (rec.latitude < -90 or rec.latitude > 90):
                raise models.ValidationError('La latitud debe estar entre -90 y 90.')
            if rec.longitude and (rec.longitude < -180 or rec.longitude > 180):
                raise models.ValidationError('La longitud debe estar entre -180 y 180.')
