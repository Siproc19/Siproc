# -*- coding: utf-8 -*-
from odoo import fields, models


class GtPayrollAdjustmentType(models.Model):
    _name = "l10n_gt.payroll.adjustment.type"
    _description = "GT Payroll Adjustment Type"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    kind = fields.Selection([
        ("earning", "Earning"),
        ("deduction", "Deduction"),
    ], required=True)
    taxable = fields.Boolean(default=True)
    active = fields.Boolean(default=True)


class GtPayrollAdjustment(models.Model):
    _name = "l10n_gt.payroll.adjustment"
    _description = "GT Payroll Adjustment"

    employee_id = fields.Many2one("hr.employee", required=True)
    version_id = fields.Many2one("hr.version", required=True, string="Salary Version")
    adjustment_type_id = fields.Many2one("l10n_gt.payroll.adjustment.type", required=True)
    date = fields.Date(required=True)
    amount = fields.Float(required=True)
    description = fields.Char()
    state = fields.Selection([
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("paid", "Paid"),
        ("cancel", "Cancelled"),
    ], default="draft")
