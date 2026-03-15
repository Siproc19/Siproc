from odoo import fields, models


class GtPayrollParameter(models.Model):
    _name = "gt.payroll.parameter"
    _description = "Parámetros Planilla Guatemala"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from desc, id desc"

    name = fields.Char(string="Nombre", required=True, tracking=True)
    active = fields.Boolean(default=True)
    date_from = fields.Date(string="Vigencia Desde", required=True, tracking=True)
    date_to = fields.Date(string="Vigencia Hasta")
    company_id = fields.Many2one("res.company", string="Compañía", default=lambda self: self.env.company)

    minimum_wage = fields.Float(string="Salario Mínimo", default=3634.59)
    incentive_bonus = fields.Float(string="Bonificación Incentivo", default=250.00)
    igss_employee_rate = fields.Float(string="IGSS Laboral %", default=4.83)
    igss_employer_rate = fields.Float(string="IGSS Patronal %", default=10.67)
    irtra_rate = fields.Float(string="IRTRA %", default=1.0)
    intecap_rate = fields.Float(string="INTECAP %", default=1.0)
    vacations_days = fields.Float(string="Días de Vacaciones", default=15.0)

    extra_hour_rate_multiplier = fields.Float(string="Multiplicador Hora Extra", default=1.5)

    isr_exempt_monthly = fields.Float(string="ISR Exento Mensual", default=4000.00)
    isr_rate_low = fields.Float(string="ISR Tramo Bajo %", default=5.0)
    isr_rate_high = fields.Float(string="ISR Tramo Alto %", default=7.0)
    isr_high_threshold = fields.Float(string="ISR Umbral Tramo Alto", default=6000.00)
