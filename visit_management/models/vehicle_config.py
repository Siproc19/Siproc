# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class VisitVehicleConfig(models.Model):
    _name        = 'visit.vehicle.config'
    _description = 'Configuración de Vehículo / Combustible'
    _order       = 'name'
    _rec_name    = 'name'

    name = fields.Char(
        string='Vehículo / Placa',
        required=True,
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Asesor Asignado',
        index=True,
    )
    vehicle_type = fields.Selection(
        selection=[
            ('car',        'Automóvil'),
            ('motorcycle', 'Motocicleta'),
            ('van',        'Camioneta'),
            ('truck',      'Camión'),
        ],
        string='Tipo de Vehículo',
        default='car',
    )
    fuel_type = fields.Selection(
        selection=[
            ('gasoline', 'Gasolina'),
            ('diesel',   'Diesel'),
            ('gas',      'Gas Natural'),
            ('electric', 'Eléctrico'),
        ],
        string='Tipo de Combustible',
        default='gasoline',
        required=True,
    )
    km_per_unit = fields.Float(
        string='KM por Galón/Litro',
        default=40.0,
        required=True,
        help='Rendimiento del vehículo: kilómetros por galón o litro de combustible.',
    )
    fuel_price = fields.Float(
        string='Precio por Galón/Litro',
        required=True,
        help='Precio actual del combustible en la moneda configurada.',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    notes  = fields.Text('Notas')
    active = fields.Boolean(default=True)

    # Estadísticas
    visit_count = fields.Integer(
        string='# Visitas',
        compute='_compute_visit_count',
    )
    total_km = fields.Float(
        string='KM Total Recorrido',
        compute='_compute_visit_count',
        digits=(10, 1),
    )
    total_fuel_cost = fields.Float(
        string='Costo Total Combustible',
        compute='_compute_visit_count',
        digits=(10, 0),
    )

    def _compute_visit_count(self):
        Visit = self.env['visit.visit']
        for rec in self:
            visits = Visit.search([
                ('vehicle_config_id', '=', rec.id),
                ('state', '=', 'done'),
            ])
            rec.visit_count      = len(visits)
            rec.total_km         = sum(visits.mapped('km_traveled'))
            rec.total_fuel_cost  = sum(visits.mapped('fuel_cost'))

    def action_view_visits(self):
        self.ensure_one()
        return {
            'type':      'ir.actions.act_window',
            'name':      _('Visitas del Vehículo'),
            'res_model': 'visit.visit',
            'view_mode': 'list,form',
            'domain':    [('vehicle_config_id', '=', self.id)],
            'context':   {'default_vehicle_config_id': self.id},
        }
