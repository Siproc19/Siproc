# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    gt_payroll_enabled = fields.Boolean(string="Habilitar planilla Guatemala", default=True)
    gt_vacation_days_per_year = fields.Float(string="Días de vacaciones por año", default=15.0)
    gt_vacation_count_mode = fields.Selection([
        ("business_days", "Días hábiles"),
        ("calendar_days", "Días calendario"),
    ], string="Tipo de conteo de vacaciones", default="business_days")
    gt_incentive_bonus_default = fields.Float(string="Bono incentivo por defecto", default=250.00)
    gt_payroll_journal_id = fields.Many2one("account.journal", string="Diario de planilla")
    gt_liquidation_journal_id = fields.Many2one("account.journal", string="Diario de liquidaciones")
