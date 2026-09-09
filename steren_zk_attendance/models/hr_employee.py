# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    zk_device_user_id = fields.Char(
        string='ID en checador ZKTeco',
        copy=False,
        help='Número de usuario asignado a este empleado dentro del checador '
             'biométrico (el mismo ID que se usó al enrolar su huella en el equipo).',
    )
