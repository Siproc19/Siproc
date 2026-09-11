# -*- coding: utf-8 -*-
from odoo import fields, models


class ZkAttendanceLog(models.Model):
    _name = 'zk.attendance.log'
    _description = 'Marcación cruda importada del checador biométrico'
    _order = 'punch_datetime desc'

    device_id = fields.Many2one(
        'zk.biometric.device', string='Checador', required=True,
        ondelete='cascade', index=True)
    device_user_id = fields.Char(string='ID de usuario en el equipo', required=True)
    employee_id = fields.Many2one('hr.employee', string='Empleado asociado')
    punch_datetime = fields.Datetime(string='Fecha y hora (UTC)', required=True)
    attendance_id = fields.Many2one(
        'hr.attendance', string='Registro de asistencia generado')

    _unique_punch = models.Constraint(
        'unique(device_id, device_user_id, punch_datetime)',
        'Esta marcación ya había sido importada anteriormente.',
    )
