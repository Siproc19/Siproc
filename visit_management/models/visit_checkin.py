# -*- coding: utf-8 -*-
from odoo import models, fields


class VisitCheckin(models.Model):
    _name = 'visit.checkin'
    _description = 'Registro GPS de Visita'
    _order = 'timestamp desc'
    _rec_name = 'visit_id'

    visit_id = fields.Many2one(
        'visit.visit',
        string='Visita',
        required=True,
        ondelete='cascade',
        index=True,
    )
    checkin_type = fields.Selection(
        selection=[('in', 'Check-In'), ('out', 'Check-Out')],
        string='Tipo',
        required=True,
    )
    timestamp  = fields.Datetime(string='Fecha/Hora', default=fields.Datetime.now)
    latitude   = fields.Float('Latitud',  digits=(10, 7))
    longitude  = fields.Float('Longitud', digits=(10, 7))
    address    = fields.Char('Direccion Detectada')
    accuracy_m = fields.Float('Precision GPS (m)', digits=(10, 1))

    employee_id = fields.Many2one(
        related='visit_id.employee_id',
        string='Asesor',
        store=True,
    )
    partner_id = fields.Many2one(
        related='visit_id.partner_id',
        string='Cliente',
        store=True,
    )
