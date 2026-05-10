# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class VisitCheckin(models.Model):
    _name        = 'visit.checkin'
    _description = 'Registro GPS de Visita (Check-In / Check-Out)'
    _order       = 'timestamp desc'
    _rec_name    = 'visit_id'

    visit_id = fields.Many2one(
        comodel_name='visit.visit',
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
    timestamp   = fields.Datetime(
        string='Fecha/Hora',
        default=fields.Datetime.now,
        required=True,
    )
    latitude    = fields.Float('Latitud',          digits=(10, 7))
    longitude   = fields.Float('Longitud',         digits=(10, 7))
    address     = fields.Char( 'Dirección Detectada')
    accuracy_m  = fields.Float('Precisión GPS (m)', digits=(10, 1))

    # Campos relacionados para reportes
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
    scheduled_date = fields.Date(
        related='visit_id.scheduled_date',
        string='Fecha Visita',
        store=True,
    )
