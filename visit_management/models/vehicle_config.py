# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class VisitVehicleConfig(models.Model):
    _name = 'visit.vehicle.config'
    _description = 'Configuracion de Vehiculo'
    _order = 'name'

    name = fields.Char(string='Vehiculo / Placa', required=True)
    employee_id = fields.Many2one('hr.employee', string='Asesor Asignado')
    vehicle_type = fields.Selection(
        selection=[
            ('car',        'Automovil'),
            ('motorcycle', 'Motocicleta'),
            ('van',        'Camioneta'),
            ('truck',      'Camion'),
        ],
        string='Tipo de Vehiculo',
        default='car',
    )
    fuel_type = fields.Selection(
        selection=[
            ('gasoline', 'Gasolina'),
            ('diesel',   'Diesel'),
            ('gas',      'Gas'),
            ('electric', 'Electrico'),
        ],
        string='Tipo de Combustible',
        default='gasoline',
        required=True,
    )
    km_per_unit = fields.Float(
        string='KM por Galon/Litro',
        default=40.0,
        required=True,
    )
    fuel_price = fields.Float(string='Precio por Galon/Litro', required=True)
    notes = fields.Text('Notas')
    active = fields.Boolean(default=True)

    visit_count = fields.Integer(
        string='Visitas',
        compute='_compute_stats',
    )
    total_km = fields.Float(
        string='KM Total',
        compute='_compute_stats',
        digits=(10, 1),
    )

    def _compute_stats(self):
        Visit = self.env['visit.visit']
        for rec in self:
            visits = Visit.search([
                ('vehicle_config_id', '=', rec.id),
                ('state', '=', 'done'),
            ])
            rec.visit_count = len(visits)
            rec.total_km = sum(visits.mapped('km_traveled'))

    def action_view_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Visitas del Vehiculo'),
            'res_model': 'visit.visit',
            'view_mode': 'list,form',
            'domain': [('vehicle_config_id', '=', self.id)],
        }
