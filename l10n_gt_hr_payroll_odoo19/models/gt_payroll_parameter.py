from odoo import fields, models

class GtPayrollParameter(models.Model):
    _name = "gt.payroll.parameter"
    _description = "Parámetros Planilla Guatemala"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date()
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    incentive_bonus = fields.Float(default=250.0)
    igss_employee_rate = fields.Float(default=4.83)
    igss_employer_rate = fields.Float(default=10.67)
    irtra_rate = fields.Float(default=1.0)
    intecap_rate = fields.Float(default=1.0)
    vacations_days = fields.Float(default=15.0)
    isr_exempt_monthly = fields.Float(default=4000.0)
    isr_rate_low = fields.Float(default=5.0)
    isr_rate_high = fields.Float(default=7.0)
    isr_high_threshold = fields.Float(default=6000.0)
