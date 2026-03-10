# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    gt_dpi = fields.Char(string="DPI")
    gt_nit = fields.Char(string="NIT")
    gt_igss_number = fields.Char(string="IGSS Number")
    gt_employee_type = fields.Selection([
        ("administrative", "Administrative"),
        ("operative", "Operative"),
        ("sales", "Sales"),
        ("temporary", "Temporary"),
        ("other", "Other"),
    ], string="GT Employee Type")
    gt_bank_id = fields.Many2one("res.bank", string="Bank")
    gt_bank_account = fields.Char(string="Bank Account")
    gt_payment_method = fields.Selection([
        ("bank_transfer", "Bank Transfer"),
        ("cash", "Cash"),
        ("check", "Check"),
        ("other", "Other"),
    ], default="bank_transfer")
    gt_cost_center_id = fields.Many2one("account.analytic.account", string="Cost Center")
    gt_labor_status = fields.Selection([
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("terminated", "Terminated"),
    ], default="active")
    gt_hire_date = fields.Date(string="Hire Date")
    gt_termination_date = fields.Date(string="Termination Date")
    gt_termination_reason = fields.Selection([
        ("resignation", "Resignation"),
        ("dismissal", "Dismissal"),
        ("mutual_agreement", "Mutual Agreement"),
        ("end_contract", "End of Contract"),
        ("death", "Death"),
        ("other", "Other"),
    ], string="Termination Reason")
