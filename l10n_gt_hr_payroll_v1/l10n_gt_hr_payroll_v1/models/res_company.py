# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    gt_payroll_enabled = fields.Boolean(string="Enable Guatemala Payroll", default=True)
    gt_vacation_days_per_year = fields.Float(default=15.0)
    gt_vacation_count_mode = fields.Selection([
        ("business_days", "Business Days"),
        ("calendar_days", "Calendar Days"),
    ], default="business_days")
    gt_incentive_bonus_default = fields.Float(default=250.00)
    gt_payroll_journal_id = fields.Many2one("account.journal", string="Payroll Journal")
    gt_liquidation_journal_id = fields.Many2one("account.journal", string="Liquidation Journal")
