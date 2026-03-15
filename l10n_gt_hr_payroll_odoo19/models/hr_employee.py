from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    gt_nit = fields.Char(string="NIT")
    gt_igss_number = fields.Char(string="No. IGSS")
    gt_bank_name = fields.Char(string="Banco")
    gt_bank_account = fields.Char(string="Cuenta Bancaria")
