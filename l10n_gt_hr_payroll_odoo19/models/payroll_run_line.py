from odoo import api, fields, models

class GtPayrollRunLine(models.Model):
    _name = "gt.payroll.run.line"
    _description = "Línea de Planilla Guatemala"
    run_id = fields.Many2one("gt.payroll.run", required=True, ondelete="cascade")
    employee_id = fields.Many2one("hr.employee", required=True)
    worked_days = fields.Float(default=15.0)
    extra_hours = fields.Float(default=0.0)
    commissions = fields.Float(string="Bonificaciones", default=0.0)
    bonuses = fields.Float(default=0.0)
    other_income = fields.Float(default=0.0)
    other_deductions = fields.Float(default=0.0)
    wage_reference = fields.Float(string="Salario Referencia", default=0.0)
    incentive_bonus = fields.Float(compute="_compute_all", store=True)
    ordinary_salary = fields.Float(compute="_compute_all", store=True)
    gross_total = fields.Float(compute="_compute_all", store=True)
    igss_employee = fields.Float(compute="_compute_all", store=True)
    isr_amount = fields.Float(compute="_compute_all", store=True)
    total_deductions = fields.Float(compute="_compute_all", store=True)
    net_total = fields.Float(compute="_compute_all", store=True)
    @api.depends("worked_days","extra_hours","commissions","bonuses","other_income","other_deductions","wage_reference","run_id.parameter_id")
    def _compute_all(self):
        for rec in self:
            wage = rec.wage_reference or 0.0
            rec.ordinary_salary = (wage/30.0)*rec.worked_days if wage else 0.0
            rec.incentive_bonus = rec.run_id.parameter_id.incentive_bonus if rec.run_id.parameter_id else 0.0
            rec.gross_total = rec.ordinary_salary + rec.incentive_bonus + rec.commissions + rec.bonuses + rec.other_income
            rate = (rec.run_id.parameter_id.igss_employee_rate or 0.0)/100.0 if rec.run_id.parameter_id else 0.0
            rec.igss_employee = rec.ordinary_salary * rate
            taxable = rec.gross_total - rec.igss_employee
            exempt = rec.run_id.parameter_id.isr_exempt_monthly if rec.run_id.parameter_id else 0.0
            rec.isr_amount = 0.0
            if taxable > exempt and rec.run_id.parameter_id:
                excess = taxable - exempt
                threshold = rec.run_id.parameter_id.isr_high_threshold
                pct = rec.run_id.parameter_id.isr_rate_low if taxable <= threshold else rec.run_id.parameter_id.isr_rate_high
                rec.isr_amount = excess * (pct/100.0)
            rec.total_deductions = rec.igss_employee + rec.isr_amount + rec.other_deductions
            rec.net_total = rec.gross_total - rec.total_deductions
