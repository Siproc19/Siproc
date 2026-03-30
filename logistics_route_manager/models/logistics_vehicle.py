# -*- coding: utf-8 -*-
from odoo import models, fields, api


class LogisticsVehicle(models.Model):
    """Vehículos disponibles para rutas logísticas."""
    _name = 'logistics.vehicle'
    _description = 'Vehículo Logístico'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(string='Nombre / Descripción', required=True, tracking=True)
    plate = fields.Char(string='Placa', required=True, tracking=True)
    vehicle_type = fields.Selection([
        ('motorcycle', 'Motocicleta'),
        ('car', 'Automóvil'),
        ('pickup', 'Pick-up'),
        ('van', 'Van / Panel'),
        ('truck', 'Camión'),
    ], string='Tipo de Vehículo', default='car', required=True)

    brand = fields.Char(string='Marca')
    model = fields.Char(string='Modelo')
    year = fields.Integer(string='Año')
    color = fields.Char(string='Color')
    capacity_kg = fields.Float(string='Capacidad (kg)')
    fuel_type = fields.Selection([
        ('gasoline', 'Gasolina'),
        ('diesel', 'Diesel'),
        ('electric', 'Eléctrico'),
        ('hybrid', 'Híbrido'),
    ], string='Tipo de Combustible', default='gasoline')

    current_driver_id = fields.Many2one(
        'logistics.driver',
        string='Conductor Actual',
        compute='_compute_current_driver',
    )
    is_available = fields.Boolean(
        string='Disponible',
        compute='_compute_is_available',
        store=True,
    )
    active = fields.Boolean(string='Activo', default=True)
    notes = fields.Text(string='Notas')
    image = fields.Binary(string='Foto del Vehículo')

    route_ids = fields.One2many(
        'logistics.route', 'vehicle_id',
        string='Rutas',
    )
    route_count = fields.Integer(
        string='Total Rutas',
        compute='_compute_route_count',
    )

    @api.depends('route_ids', 'route_ids.state')
    def _compute_current_driver(self):
        for rec in self:
            active_route = rec.route_ids.filtered(
                lambda r: r.state == 'in_progress'
            )
            rec.current_driver_id = active_route[0].driver_id if active_route else False

    @api.depends('route_ids', 'route_ids.state')
    def _compute_is_available(self):
        for rec in self:
            active = rec.route_ids.filtered(
                lambda r: r.state in ('confirmed', 'in_progress')
            )
            rec.is_available = not bool(active)

    @api.depends('route_ids')
    def _compute_route_count(self):
        for rec in self:
            rec.route_count = len(rec.route_ids)
